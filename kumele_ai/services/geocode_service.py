"""
Geocode Service - OpenStreetMap Nominatim integration for geocoding
"""
import logging
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
import httpx
import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class GeocodeService:
    """
    Service for geocoding addresses using OpenStreetMap Nominatim.
    
    Features:
    - Forward geocoding: address string -> lat/lon
    - Redis caching with configurable TTL
    - Rate limiting (respects Nominatim usage policy)
    - Robust timeouts and retries
    """
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._last_request_time: float = 0
        self._min_request_interval: float = 1.0  # Nominatim requires 1 request/sec max
    
    def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis client for caching"""
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
                self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis unavailable for geocode caching: {e}")
                self._redis_client = None
        return self._redis_client
    
    def _get_cache_key(self, address: str) -> str:
        """Generate cache key for address"""
        address_hash = hashlib.sha256(address.lower().strip().encode()).hexdigest()[:32]
        return f"geocode:{address_hash}"
    
    def _get_cached_result(self, address: str) -> Optional[Dict[str, Any]]:
        """Get cached geocoding result"""
        try:
            r = self._get_redis()
            if r:
                cache_key = self._get_cache_key(address)
                cached = r.get(cache_key)
                if cached:
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        return None
    
    def _set_cached_result(self, address: str, result: Dict[str, Any]) -> None:
        """Cache geocoding result"""
        try:
            r = self._get_redis()
            if r:
                cache_key = self._get_cache_key(address)
                r.setex(
                    cache_key,
                    settings.NOMINATIM_CACHE_TTL_SEC,
                    json.dumps(result)
                )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting for Nominatim API"""
        import time
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))
    )
    def _make_nominatim_request(self, address: str) -> Dict[str, Any]:
        """Make request to Nominatim API with retries"""
        self._rate_limit()
        
        headers = {
            "User-Agent": settings.NOMINATIM_USER_AGENT,
            "Accept": "application/json"
        }
        
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        
        with httpx.Client(timeout=settings.NOMINATIM_TIMEOUT_SEC) as client:
            response = client.get(
                f"{settings.NOMINATIM_URL}/search",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Forward geocode an address string to lat/lon coordinates.
        
        Args:
            address: Address string (e.g., "New York, NY" or "123 Main St, Seattle")
            
        Returns:
            Dict with lat, lon, display_name, and address details, or None if not found
        """
        if not address or not address.strip():
            return None
        
        address = address.strip()
        
        # Check cache first
        cached = self._get_cached_result(address)
        if cached:
            logger.debug(f"Geocode cache hit for: {address}")
            return cached
        
        try:
            results = self._make_nominatim_request(address)
            
            if not results:
                logger.info(f"No geocode results for: {address}")
                # Cache empty result to avoid repeated lookups
                empty_result = {"found": False, "address": address}
                self._set_cached_result(address, empty_result)
                return None
            
            result = results[0]
            geocode_result = {
                "found": True,
                "address": address,
                "latitude": float(result.get("lat", 0)),
                "longitude": float(result.get("lon", 0)),
                "display_name": result.get("display_name", ""),
                "place_id": result.get("place_id"),
                "osm_type": result.get("osm_type"),
                "osm_id": result.get("osm_id"),
                "address_details": result.get("address", {}),
                "importance": result.get("importance", 0)
            }
            
            # Cache successful result
            self._set_cached_result(address, geocode_result)
            
            logger.info(f"Geocoded '{address}' -> ({geocode_result['latitude']}, {geocode_result['longitude']})")
            return geocode_result
            
        except httpx.TimeoutException:
            logger.error(f"Geocode timeout for: {address}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Geocode HTTP error for {address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Geocode error for {address}: {e}")
            return None
    
    def geocode_to_coords(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Convenience method to get just lat/lon tuple.
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        result = self.geocode(address)
        if result and result.get("found"):
            return (result["latitude"], result["longitude"])
        return None
    
    def batch_geocode(self, addresses: list) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Geocode multiple addresses.
        
        Note: Due to Nominatim rate limits, this will be slow for large batches.
        
        Args:
            addresses: List of address strings
            
        Returns:
            Dict mapping addresses to geocode results
        """
        results = {}
        for address in addresses:
            results[address] = self.geocode(address)
        return results


# Singleton instance
geocode_service = GeocodeService()
