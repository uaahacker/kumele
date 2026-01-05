-- Kumele AI/ML Backend - Data Loading Script
-- This script loads synthetic data into PostgreSQL
-- Run from psql: \i /tmp/load_data.sql

-- =============================================================================
-- 1. USERS (100 users)
-- Schema: user_id (auto), name, email, age, gender, location_lat, location_lon, preferred_language, created_at
-- =============================================================================
INSERT INTO users (name, email, age, gender, location_lat, location_lon, preferred_language, created_at) VALUES
('Alex Smith', 'user1@example.com', 28, 'male', 51.5074, -0.1278, 'en', '2025-06-15 10:30:00'),
('Jordan Johnson', 'user2@example.com', 34, 'female', 40.7128, -74.0060, 'en', '2025-07-20 14:45:00'),
('Taylor Williams', 'user3@example.com', 25, 'other', 48.8566, 2.3522, 'fr', '2025-08-05 09:15:00'),
('Morgan Brown', 'user4@example.com', 42, 'male', 35.6762, 139.6503, 'en', '2025-05-10 16:20:00'),
('Casey Jones', 'user5@example.com', 31, 'female', -33.8688, 151.2093, 'en', '2025-09-01 11:00:00'),
('Riley Garcia', 'user6@example.com', 29, 'male', 25.2048, 55.2708, 'ar', '2025-04-22 08:30:00'),
('Quinn Miller', 'user7@example.com', 36, 'female', 52.5200, 13.4050, 'de', '2025-10-15 13:45:00'),
('Avery Davis', 'user8@example.com', 27, 'other', 43.6532, -79.3832, 'en', '2025-03-18 15:30:00'),
('Skyler Rodriguez', 'user9@example.com', 33, 'male', 1.3521, 103.8198, 'en', '2025-11-05 10:00:00'),
('Parker Martinez', 'user10@example.com', 39, 'female', 19.0760, 72.8777, 'en', '2025-02-28 12:15:00'),
('Jamie Wilson', 'user11@example.com', 24, 'male', 51.4545, -0.0983, 'en', '2025-06-20 09:30:00'),
('Drew Anderson', 'user12@example.com', 30, 'female', 40.7589, -73.9851, 'en', '2025-07-15 14:00:00'),
('Reese Taylor', 'user13@example.com', 45, 'male', 48.9012, 2.3344, 'fr', '2025-08-10 16:45:00'),
('Sage Thomas', 'user14@example.com', 28, 'female', 35.7101, 139.7321, 'en', '2025-05-25 11:30:00'),
('Finley Moore', 'user15@example.com', 35, 'other', -33.9012, 151.1890, 'en', '2025-09-12 08:15:00'),
('Rowan Jackson', 'user16@example.com', 41, 'male', 25.1890, 55.3012, 'ar', '2025-04-30 13:00:00'),
('Hayden Martin', 'user17@example.com', 26, 'female', 52.4856, 13.3901, 'de', '2025-10-20 15:45:00'),
('Emery Lee', 'user18@example.com', 32, 'male', 43.6891, -79.4012, 'en', '2025-03-25 10:30:00'),
('Phoenix Thompson', 'user19@example.com', 38, 'female', 1.3301, 103.7891, 'en', '2025-11-10 12:00:00'),
('River White', 'user20@example.com', 29, 'other', 19.1012, 72.9012, 'en', '2025-02-15 14:30:00'),
('Alex Harris', 'user21@example.com', 27, 'male', 51.5234, -0.1456, 'en', '2025-06-25 09:00:00'),
('Jordan Clark', 'user22@example.com', 33, 'female', 40.6892, -74.0234, 'en', '2025-07-22 13:30:00'),
('Taylor Lewis', 'user23@example.com', 44, 'male', 48.8123, 2.3678, 'fr', '2025-08-15 16:00:00'),
('Morgan Robinson', 'user24@example.com', 31, 'female', 35.6543, 139.6234, 'en', '2025-05-30 11:15:00'),
('Casey Walker', 'user25@example.com', 36, 'other', -33.8456, 151.2234, 'en', '2025-09-18 08:45:00'),
('Riley Hall', 'user26@example.com', 40, 'male', 25.2234, 55.2456, 'ar', '2025-04-15 13:15:00'),
('Quinn Allen', 'user27@example.com', 25, 'female', 52.5345, 13.4234, 'de', '2025-10-25 15:00:00'),
('Avery Young', 'user28@example.com', 34, 'male', 43.6234, -79.3567, 'en', '2025-03-30 10:45:00'),
('Skyler King', 'user29@example.com', 29, 'female', 1.3678, 103.8345, 'en', '2025-11-15 11:45:00'),
('Parker Wright', 'user30@example.com', 37, 'other', 19.0567, 72.8567, 'en', '2025-02-20 14:15:00'),
('Jamie Scott', 'user31@example.com', 28, 'male', 51.4890, -0.1123, 'en', '2025-06-30 09:45:00'),
('Drew Green', 'user32@example.com', 42, 'female', 40.7345, -73.9678, 'en', '2025-07-28 14:30:00'),
('Reese Adams', 'user33@example.com', 30, 'male', 48.8789, 2.3123, 'fr', '2025-08-20 16:15:00'),
('Sage Baker', 'user34@example.com', 35, 'female', 35.6890, 139.6678, 'en', '2025-06-05 11:00:00'),
('Finley Nelson', 'user35@example.com', 26, 'other', -33.8789, 151.1678, 'en', '2025-09-25 08:30:00'),
('Rowan Hill', 'user36@example.com', 39, 'male', 25.1678, 55.2890, 'ar', '2025-05-02 13:45:00'),
('Hayden Campbell', 'user37@example.com', 33, 'female', 52.5012, 13.3678, 'de', '2025-10-30 15:30:00'),
('Emery Mitchell', 'user38@example.com', 41, 'male', 43.6567, -79.4234, 'en', '2025-04-05 10:15:00'),
('Phoenix Roberts', 'user39@example.com', 27, 'female', 1.3456, 103.8012, 'en', '2025-11-20 12:30:00'),
('River Carter', 'user40@example.com', 32, 'other', 19.0890, 72.8890, 'en', '2025-03-01 14:00:00'),
('Alex Phillips', 'user41@example.com', 38, 'male', 51.5345, -0.1567, 'en', '2025-07-05 09:15:00'),
('Jordan Evans', 'user42@example.com', 24, 'female', 40.7012, -74.0456, 'en', '2025-08-01 13:45:00'),
('Taylor Turner', 'user43@example.com', 43, 'male', 48.8456, 2.3890, 'fr', '2025-09-05 16:30:00'),
('Morgan Collins', 'user44@example.com', 29, 'female', 35.6234, 139.6567, 'en', '2025-06-10 11:30:00'),
('Casey Edwards', 'user45@example.com', 34, 'other', -33.8234, 151.2456, 'en', '2025-10-05 08:00:00'),
('Riley Stewart', 'user46@example.com', 36, 'male', 25.2345, 55.2234, 'ar', '2025-05-08 13:30:00'),
('Quinn Sanchez', 'user47@example.com', 31, 'female', 52.5456, 13.4456, 'de', '2025-11-05 15:15:00'),
('Avery Morris', 'user48@example.com', 40, 'male', 43.6890, -79.3890, 'en', '2025-04-10 10:00:00'),
('Skyler Rogers', 'user49@example.com', 26, 'female', 1.3890, 103.8567, 'en', '2025-12-01 12:15:00'),
('Parker Reed', 'user50@example.com', 35, 'other', 19.0345, 72.8234, 'en', '2025-03-05 14:45:00');

-- =============================================================================
-- 2. EVENTS (100 events) - depends on users
-- Schema: event_id (auto), host_id, title, description, category, location, location_lat, location_lon, capacity, price, event_date, status, created_at
-- =============================================================================
INSERT INTO events (host_id, title, description, category, location, location_lat, location_lon, capacity, price, event_date, status, created_at) VALUES
(1, 'Italian Pasta Masterclass', 'Learn to make authentic Italian pasta from scratch!', 'cooking', 'London, UK', 51.5074, -0.1278, 15, 25.00, '2026-01-15 18:00:00', 'scheduled', '2025-12-01 10:00:00'),
(2, 'Street Photography Walk', 'Explore urban photography techniques in NYC', 'photography', 'New York, USA', 40.7128, -74.0060, 20, 0.00, '2026-01-20 10:00:00', 'scheduled', '2025-12-05 14:00:00'),
(3, 'Morning Yoga Flow', 'Start your day with energizing yoga', 'yoga', 'Paris, France', 48.8566, 2.3522, 25, 15.00, '2026-01-12 07:00:00', 'scheduled', '2025-12-03 09:00:00'),
(4, 'Python Workshop', 'Introduction to Python programming', 'tech', 'Tokyo, Japan', 35.6762, 139.6503, 30, 0.00, '2026-01-25 14:00:00', 'scheduled', '2025-12-08 11:00:00'),
(5, 'Acoustic Jam Session', 'Bring your instrument and jam!', 'music', 'Sydney, Australia', -33.8688, 151.2093, 20, 10.00, '2026-01-18 19:00:00', 'scheduled', '2025-12-06 15:00:00'),
(6, 'HIIT Workout Class', 'High intensity interval training', 'fitness', 'Dubai, UAE', 25.2048, 55.2708, 25, 20.00, '2026-01-22 06:30:00', 'scheduled', '2025-12-10 08:00:00'),
(7, 'Board Game Night', 'Strategy games and socializing', 'gaming', 'Berlin, Germany', 52.5200, 13.4050, 15, 0.00, '2026-01-17 18:30:00', 'scheduled', '2025-12-04 16:00:00'),
(8, 'Sushi Making Workshop', 'Learn to roll your own sushi', 'cooking', 'Toronto, Canada', 43.6532, -79.3832, 12, 45.00, '2026-01-28 17:00:00', 'scheduled', '2025-12-12 10:00:00'),
(9, 'Portrait Photography 101', 'Master portrait lighting and composition', 'photography', 'Singapore', 1.3521, 103.8198, 15, 30.00, '2026-02-01 14:00:00', 'scheduled', '2025-12-15 13:00:00'),
(10, 'Meditation & Mindfulness', 'Find inner peace and reduce stress', 'yoga', 'Mumbai, India', 19.0760, 72.8777, 30, 0.00, '2026-01-14 08:00:00', 'scheduled', '2025-12-02 07:00:00'),
(1, 'Vegan Cooking Night', 'Delicious plant-based recipes', 'cooking', 'London, UK', 51.5123, -0.1345, 15, 20.00, '2026-02-05 18:30:00', 'scheduled', '2025-12-18 11:00:00'),
(2, 'Night Photography Tour', 'Capture the city lights', 'photography', 'New York, USA', 40.7234, -73.9890, 12, 25.00, '2026-02-10 20:00:00', 'scheduled', '2025-12-20 14:00:00'),
(3, 'Power Yoga Session', 'Build strength through yoga', 'yoga', 'Paris, France', 48.8456, 2.3678, 20, 18.00, '2026-01-30 09:00:00', 'scheduled', '2025-12-14 09:00:00'),
(4, 'AI/ML Discussion', 'Explore artificial intelligence trends', 'tech', 'Tokyo, Japan', 35.6890, 139.6234, 40, 0.00, '2026-02-08 15:00:00', 'scheduled', '2025-12-22 16:00:00'),
(5, 'Guitar for Beginners', 'Learn basic guitar chords', 'music', 'Sydney, Australia', -33.8567, 151.2234, 10, 35.00, '2026-02-02 16:00:00', 'scheduled', '2025-12-16 10:00:00'),
(6, 'CrossFit Intro', 'Introduction to CrossFit training', 'fitness', 'Dubai, UAE', 25.2234, 55.2567, 20, 25.00, '2026-02-12 07:00:00', 'scheduled', '2025-12-24 08:00:00'),
(7, 'Esports Tournament', 'Competitive gaming event', 'gaming', 'Berlin, Germany', 52.5123, 13.4234, 50, 10.00, '2026-02-15 12:00:00', 'scheduled', '2025-12-26 15:00:00'),
(8, 'BBQ & Grill Session', 'Master the art of grilling', 'cooking', 'Toronto, Canada', 43.6678, -79.3567, 20, 30.00, '2026-02-20 17:00:00', 'scheduled', '2025-12-28 11:00:00'),
(9, 'Photo Editing Workshop', 'Learn Lightroom and Photoshop', 'photography', 'Singapore', 1.3456, 103.8456, 18, 40.00, '2026-02-25 13:00:00', 'scheduled', '2025-12-30 14:00:00'),
(10, 'Yoga in the Park', 'Outdoor yoga experience', 'yoga', 'Mumbai, India', 19.0890, 72.8890, 50, 0.00, '2026-01-26 07:30:00', 'scheduled', '2025-12-11 08:00:00'),
(11, 'Web Dev Meetup', 'Frontend and backend discussions', 'tech', 'London, UK', 51.4890, -0.1234, 35, 0.00, '2026-01-19 18:00:00', 'scheduled', '2025-12-07 17:00:00'),
(12, 'Open Mic Night', 'Showcase your musical talent', 'music', 'New York, USA', 40.7456, -73.9567, 30, 5.00, '2026-01-24 20:00:00', 'scheduled', '2025-12-09 19:00:00'),
(13, 'Running Club Meetup', 'Join our weekly 5K run', 'fitness', 'Paris, France', 48.8789, 2.3123, 40, 0.00, '2026-01-21 07:00:00', 'scheduled', '2025-12-13 06:00:00'),
(14, 'Retro Gaming Meetup', 'Classic console gaming', 'gaming', 'Tokyo, Japan', 35.6567, 139.6789, 25, 0.00, '2026-02-03 15:00:00', 'scheduled', '2025-12-17 14:00:00'),
(15, 'Startup Networking', 'Connect with entrepreneurs', 'tech', 'Sydney, Australia', -33.8789, 151.1890, 50, 15.00, '2026-02-07 18:00:00', 'scheduled', '2025-12-19 16:00:00'),
(1, 'Weekend Cooking Class', 'Family-friendly recipes', 'cooking', 'London, UK', 51.5012, -0.1567, 18, 35.00, '2025-12-20 11:00:00', 'completed', '2025-11-15 10:00:00'),
(2, 'Landscape Photography', 'Capture beautiful scenery', 'photography', 'New York, USA', 40.7890, -74.0123, 15, 20.00, '2025-12-15 09:00:00', 'completed', '2025-11-10 13:00:00'),
(3, 'Sunrise Yoga', 'Wake up with the sun', 'yoga', 'Paris, France', 48.8234, 2.3456, 20, 12.00, '2025-12-18 06:30:00', 'completed', '2025-11-12 07:00:00'),
(4, 'Data Science Workshop', 'Introduction to data analysis', 'tech', 'Tokyo, Japan', 35.6456, 139.6890, 30, 0.00, '2025-12-22 14:00:00', 'completed', '2025-11-20 15:00:00'),
(5, 'Music Production Intro', 'Learn DAW basics', 'music', 'Sydney, Australia', -33.8456, 151.2012, 12, 50.00, '2025-12-12 17:00:00', 'completed', '2025-11-08 14:00:00'),
(16, 'Mountain Trail Adventure', 'Guided hiking experience', 'hiking', 'Berlin, Germany', 52.4567, 13.3890, 12, 15.00, '2026-01-27 08:00:00', 'scheduled', '2025-12-21 09:00:00'),
(17, 'Sunrise Hike', 'Early morning nature walk', 'hiking', 'Toronto, Canada', 43.7012, -79.4123, 20, 0.00, '2026-02-09 06:00:00', 'scheduled', '2025-12-23 07:00:00'),
(18, 'Nature Photography Hike', 'Combine hiking with photography', 'hiking', 'Singapore', 1.3234, 103.7890, 15, 25.00, '2026-02-14 07:30:00', 'scheduled', '2025-12-25 10:00:00'),
(19, 'Beginner Hiking Group', 'Easy trails for newcomers', 'hiking', 'Mumbai, India', 19.0456, 72.8567, 25, 0.00, '2026-02-22 07:00:00', 'scheduled', '2025-12-27 08:00:00'),
(20, 'VR Gaming Experience', 'Try the latest VR games', 'gaming', 'London, UK', 51.5234, -0.0890, 10, 30.00, '2026-02-28 14:00:00', 'scheduled', '2025-12-29 15:00:00'),
(21, 'Strength Training Basics', 'Learn proper form and technique', 'fitness', 'New York, USA', 40.7567, -73.9234, 20, 25.00, '2026-03-01 10:00:00', 'scheduled', '2025-12-31 11:00:00'),
(22, 'Thai Cooking Class', 'Authentic Thai cuisine', 'cooking', 'Paris, France', 48.8678, 2.2890, 15, 40.00, '2026-03-05 18:00:00', 'scheduled', '2026-01-02 12:00:00'),
(23, 'Portrait Masterclass', 'Advanced portrait techniques', 'photography', 'Tokyo, Japan', 35.7012, 139.7123, 10, 60.00, '2026-03-10 13:00:00', 'scheduled', '2026-01-03 14:00:00'),
(24, 'Meditation Retreat', 'Full day of mindfulness', 'yoga', 'Sydney, Australia', -33.8123, 151.2345, 30, 75.00, '2026-03-15 09:00:00', 'scheduled', '2026-01-04 09:00:00'),
(25, 'Blockchain Workshop', 'Understanding crypto and Web3', 'tech', 'Dubai, UAE', 25.1890, 55.3012, 40, 0.00, '2026-03-20 16:00:00', 'scheduled', '2026-01-05 16:00:00'),
(26, 'Jazz Night', 'Live jazz and refreshments', 'music', 'Berlin, Germany', 52.5345, 13.3567, 50, 15.00, '2025-12-10 20:00:00', 'completed', '2025-11-05 18:00:00'),
(27, 'Morning Run Club', 'Start the day with exercise', 'fitness', 'Toronto, Canada', 43.6345, -79.3234, 30, 0.00, '2025-12-08 06:30:00', 'completed', '2025-11-01 06:00:00'),
(28, 'Card Game Tournament', 'Poker and strategy games', 'gaming', 'Singapore', 1.2890, 103.8234, 24, 20.00, '2025-12-05 19:00:00', 'completed', '2025-10-28 17:00:00'),
(29, 'Mexican Cuisine Night', 'Tacos, burritos, and more', 'cooking', 'Mumbai, India', 19.1012, 72.8123, 20, 25.00, '2025-12-02 18:30:00', 'completed', '2025-10-25 11:00:00'),
(30, 'Wildlife Photography', 'Capture animals in their habitat', 'photography', 'London, UK', 51.4678, -0.1678, 12, 45.00, '2025-11-28 08:00:00', 'completed', '2025-10-20 09:00:00'),
(31, 'Candlelight Yoga', 'Evening relaxation session', 'yoga', 'New York, USA', 40.6890, -74.0345, 25, 20.00, '2025-11-25 19:00:00', 'completed', '2025-10-18 20:00:00'),
(32, 'Cyber Security Talk', 'Protecting your digital life', 'tech', 'Paris, France', 48.8123, 2.3789, 45, 0.00, '2025-11-22 18:00:00', 'completed', '2025-10-15 17:00:00'),
(33, 'Drum Circle', 'Community percussion session', 'music', 'Tokyo, Japan', 35.6234, 139.6456, 20, 0.00, '2025-11-20 17:00:00', 'completed', '2025-10-12 16:00:00'),
(34, 'Yoga for Athletes', 'Flexibility and recovery', 'fitness', 'Sydney, Australia', -33.8567, 151.1567, 20, 22.00, '2025-11-18 16:00:00', 'completed', '2025-10-10 15:00:00');

-- =============================================================================
-- 3. EVENT RATINGS - depends on events and users
-- Schema: id (UUID auto), event_id, user_id, communication, respect, professionalism, atmosphere, value_for_money, comment, moderation_status, created_at
-- =============================================================================
INSERT INTO event_ratings (event_id, user_id, communication, respect, professionalism, atmosphere, value_for_money, comment, moderation_status, created_at) VALUES
(26, 11, 5.0, 5.0, 4.5, 5.0, 4.0, 'Amazing jazz night! The musicians were incredible.', 'approved', '2025-12-11 10:00:00'),
(26, 12, 4.5, 5.0, 5.0, 4.5, 4.5, 'Great atmosphere and lovely venue.', 'approved', '2025-12-11 11:00:00'),
(26, 13, 4.0, 4.0, 4.0, 4.5, 3.5, 'Good music, but a bit crowded.', 'approved', '2025-12-11 12:00:00'),
(27, 14, 5.0, 5.0, 5.0, 5.0, NULL, 'Best running group in the city!', 'approved', '2025-12-09 08:00:00'),
(27, 15, 4.5, 4.5, 4.5, 4.5, NULL, 'Well organized morning run.', 'approved', '2025-12-09 09:00:00'),
(28, 16, 4.0, 4.5, 4.0, 4.5, 4.0, 'Fun tournament, will come again.', 'approved', '2025-12-06 22:00:00'),
(28, 17, 4.5, 5.0, 4.5, 5.0, 4.5, 'Met great people and had fun.', 'approved', '2025-12-06 23:00:00'),
(29, 18, 5.0, 5.0, 5.0, 5.0, 5.0, 'Delicious food and great host!', 'approved', '2025-12-03 21:00:00'),
(29, 19, 4.5, 4.5, 4.5, 4.5, 4.5, 'Learned so much about Mexican cooking.', 'approved', '2025-12-03 22:00:00'),
(30, 20, 4.0, 4.5, 5.0, 4.0, 4.0, 'Great photography tips.', 'approved', '2025-11-29 12:00:00'),
(30, 21, 5.0, 5.0, 5.0, 4.5, 5.0, 'Best wildlife photography experience!', 'approved', '2025-11-29 13:00:00'),
(31, 22, 5.0, 5.0, 5.0, 5.0, 5.0, 'So peaceful and relaxing.', 'approved', '2025-11-26 21:00:00'),
(31, 23, 4.5, 4.5, 4.5, 5.0, 4.5, 'Perfect evening yoga session.', 'approved', '2025-11-26 22:00:00'),
(32, 24, 4.0, 4.0, 5.0, 4.0, NULL, 'Very informative talk.', 'approved', '2025-11-23 20:00:00'),
(32, 25, 4.5, 4.5, 5.0, 4.5, NULL, 'Learned a lot about security.', 'approved', '2025-11-23 21:00:00'),
(33, 26, 5.0, 5.0, 4.5, 5.0, NULL, 'Love the drum circle energy!', 'approved', '2025-11-21 19:00:00'),
(33, 27, 4.5, 5.0, 4.5, 5.0, NULL, 'Great community experience.', 'approved', '2025-11-21 20:00:00'),
(34, 28, 4.0, 4.5, 4.5, 4.0, 4.0, 'Good yoga for my training recovery.', 'approved', '2025-11-19 18:00:00'),
(34, 29, 4.5, 4.5, 4.5, 4.5, 4.5, 'Perfect for athletes.', 'approved', '2025-11-19 19:00:00'),
(26, 30, 4.5, 4.5, 4.5, 4.5, 4.0, 'Enjoyed the jazz night immensely.', 'approved', '2025-12-11 14:00:00');

-- =============================================================================
-- 4. USER INTERACTIONS - depends on users and events
-- Schema: id (auto), user_id, item_type, item_id, interaction_type, score, created_at
-- =============================================================================
INSERT INTO user_interactions (user_id, item_type, item_id, interaction_type, score, created_at) VALUES
(1, 'event', 1, 'view', 1.0, '2025-12-01 12:00:00'),
(1, 'event', 1, 'rsvp', 2.0, '2025-12-01 12:05:00'),
(2, 'event', 2, 'view', 1.0, '2025-12-05 15:00:00'),
(2, 'event', 2, 'click', 1.5, '2025-12-05 15:02:00'),
(2, 'event', 2, 'rsvp', 2.0, '2025-12-05 15:10:00'),
(3, 'event', 3, 'view', 1.0, '2025-12-03 10:00:00'),
(3, 'event', 3, 'rsvp', 2.0, '2025-12-03 10:15:00'),
(4, 'event', 4, 'view', 1.0, '2025-12-08 12:00:00'),
(4, 'event', 4, 'rsvp', 2.0, '2025-12-08 12:30:00'),
(5, 'event', 5, 'view', 1.0, '2025-12-06 16:00:00'),
(5, 'event', 5, 'like', 1.5, '2025-12-06 16:02:00'),
(5, 'event', 5, 'rsvp', 2.0, '2025-12-06 16:20:00'),
(6, 'event', 6, 'view', 1.0, '2025-12-10 09:00:00'),
(6, 'event', 6, 'rsvp', 2.0, '2025-12-10 09:15:00'),
(7, 'event', 7, 'view', 1.0, '2025-12-04 17:00:00'),
(7, 'event', 7, 'click', 1.5, '2025-12-04 17:05:00'),
(7, 'event', 7, 'rsvp', 2.0, '2025-12-04 17:15:00'),
(8, 'event', 8, 'view', 1.0, '2025-12-12 11:00:00'),
(8, 'event', 8, 'rsvp', 2.0, '2025-12-12 11:30:00'),
(9, 'event', 9, 'view', 1.0, '2025-12-15 14:00:00'),
(9, 'event', 9, 'rsvp', 2.0, '2025-12-15 14:30:00'),
(10, 'event', 10, 'view', 1.0, '2025-12-02 08:00:00'),
(10, 'event', 10, 'rsvp', 2.0, '2025-12-02 08:15:00'),
(11, 'hobby', 1, 'view', 1.0, '2025-12-01 10:00:00'),
(11, 'hobby', 1, 'like', 1.5, '2025-12-01 10:05:00'),
(12, 'hobby', 2, 'view', 1.0, '2025-12-02 11:00:00'),
(12, 'hobby', 2, 'like', 1.5, '2025-12-02 11:10:00'),
(13, 'hobby', 3, 'view', 1.0, '2025-12-03 12:00:00'),
(14, 'hobby', 4, 'view', 1.0, '2025-12-04 13:00:00'),
(14, 'hobby', 4, 'like', 1.5, '2025-12-04 13:15:00'),
(15, 'event', 26, 'view', 1.0, '2025-12-09 18:00:00'),
(15, 'event', 26, 'attend', 3.0, '2025-12-10 20:00:00'),
(16, 'event', 27, 'view', 1.0, '2025-12-07 06:00:00'),
(16, 'event', 27, 'attend', 3.0, '2025-12-08 07:00:00'),
(17, 'event', 28, 'view', 1.0, '2025-12-04 18:00:00'),
(17, 'event', 28, 'attend', 3.0, '2025-12-05 19:00:00'),
(18, 'event', 29, 'view', 1.0, '2025-11-30 17:00:00'),
(18, 'event', 29, 'attend', 3.0, '2025-12-02 18:30:00'),
(19, 'event', 30, 'view', 1.0, '2025-11-25 07:00:00'),
(19, 'event', 30, 'attend', 3.0, '2025-11-28 08:00:00'),
(20, 'event', 31, 'view', 1.0, '2025-11-22 18:00:00'),
(20, 'event', 31, 'attend', 3.0, '2025-11-25 19:00:00'),
(21, 'event', 1, 'view', 1.0, '2025-12-10 14:00:00'),
(21, 'event', 1, 'click', 1.5, '2025-12-10 14:05:00'),
(22, 'event', 2, 'view', 1.0, '2025-12-11 15:00:00'),
(22, 'event', 2, 'like', 1.5, '2025-12-11 15:10:00'),
(23, 'event', 3, 'view', 1.0, '2025-12-12 09:00:00'),
(23, 'event', 3, 'rsvp', 2.0, '2025-12-12 09:30:00'),
(24, 'event', 4, 'view', 1.0, '2025-12-13 12:00:00'),
(24, 'event', 4, 'click', 1.5, '2025-12-13 12:10:00');

-- =============================================================================
-- 5. USER ACTIVITIES - depends on users and events
-- Schema: id (auto), user_id, activity_type, event_id, activity_date, success
-- =============================================================================
INSERT INTO user_activities (user_id, activity_type, event_id, activity_date, success) VALUES
(1, 'event_created', 1, '2025-12-01 10:00:00', true),
(1, 'event_created', 11, '2025-12-18 11:00:00', true),
(1, 'event_created', 26, '2025-11-15 10:00:00', true),
(2, 'event_created', 2, '2025-12-05 14:00:00', true),
(2, 'event_created', 12, '2025-12-20 14:00:00', true),
(2, 'event_created', 27, '2025-11-10 13:00:00', true),
(3, 'event_created', 3, '2025-12-03 09:00:00', true),
(3, 'event_created', 13, '2025-12-14 09:00:00', true),
(3, 'event_created', 28, '2025-11-12 07:00:00', true),
(4, 'event_created', 4, '2025-12-08 11:00:00', true),
(4, 'event_created', 14, '2025-12-22 16:00:00', true),
(4, 'event_created', 29, '2025-11-20 15:00:00', true),
(5, 'event_created', 5, '2025-12-06 15:00:00', true),
(5, 'event_created', 15, '2025-12-16 10:00:00', true),
(5, 'event_created', 30, '2025-11-08 14:00:00', true),
(11, 'event_attended', 26, '2025-12-10 20:00:00', true),
(12, 'event_attended', 26, '2025-12-10 20:00:00', true),
(13, 'event_attended', 26, '2025-12-10 20:00:00', true),
(14, 'event_attended', 27, '2025-12-08 06:30:00', true),
(15, 'event_attended', 27, '2025-12-08 06:30:00', true),
(16, 'event_attended', 28, '2025-12-05 19:00:00', true),
(17, 'event_attended', 28, '2025-12-05 19:00:00', true),
(18, 'event_attended', 29, '2025-12-02 18:30:00', true),
(19, 'event_attended', 29, '2025-12-02 18:30:00', true),
(20, 'event_attended', 30, '2025-11-28 08:00:00', true),
(21, 'event_attended', 30, '2025-11-28 08:00:00', true),
(22, 'event_attended', 31, '2025-11-25 19:00:00', true),
(23, 'event_attended', 31, '2025-11-25 19:00:00', true),
(24, 'event_attended', 32, '2025-11-22 18:00:00', true),
(25, 'event_attended', 32, '2025-11-22 18:00:00', true);

-- =============================================================================
-- 6. REWARD COUPONS - depends on users
-- Schema: coupon_id (UUID auto), user_id, status_level, discount_value, stackable, is_redeemed, redeemed_at, redeemed_event_id, issued_at, expires_at
-- =============================================================================
INSERT INTO reward_coupons (user_id, status_level, discount_value, stackable, is_redeemed, issued_at, expires_at) VALUES
(1, 'gold', 8.00, true, false, '2025-12-15 10:00:00', '2026-02-15 10:00:00'),
(2, 'gold', 8.00, true, false, '2025-12-16 11:00:00', '2026-02-16 11:00:00'),
(3, 'silver', 4.00, false, false, '2025-12-17 12:00:00', '2026-02-17 12:00:00'),
(4, 'silver', 4.00, false, false, '2025-12-18 13:00:00', '2026-02-18 13:00:00'),
(5, 'gold', 8.00, true, false, '2025-12-19 14:00:00', '2026-02-19 14:00:00'),
(11, 'bronze', 0.00, false, false, '2025-12-20 10:00:00', '2026-02-20 10:00:00'),
(12, 'bronze', 0.00, false, false, '2025-12-21 11:00:00', '2026-02-21 11:00:00'),
(13, 'silver', 4.00, false, true, '2025-12-01 10:00:00', '2026-02-01 10:00:00'),
(14, 'bronze', 0.00, false, true, '2025-11-15 10:00:00', '2026-01-15 10:00:00'),
(15, 'silver', 4.00, false, false, '2025-12-22 12:00:00', '2026-02-22 12:00:00');

-- =============================================================================
-- 7. TIMESERIES DAILY - for forecasting
-- Schema: id (auto), ds (date), y (value), category, location, metric_type, created_at
-- =============================================================================
INSERT INTO timeseries_daily (ds, y, category, location, metric_type, created_at) VALUES
('2025-11-01', 45.00, 'cooking', 'London', 'attendance', '2025-11-02 00:00:00'),
('2025-11-02', 52.00, 'cooking', 'London', 'attendance', '2025-11-03 00:00:00'),
('2025-11-03', 38.00, 'cooking', 'London', 'attendance', '2025-11-04 00:00:00'),
('2025-11-04', 61.00, 'cooking', 'London', 'attendance', '2025-11-05 00:00:00'),
('2025-11-05', 55.00, 'cooking', 'London', 'attendance', '2025-11-06 00:00:00'),
('2025-11-01', 30.00, 'yoga', 'Paris', 'attendance', '2025-11-02 00:00:00'),
('2025-11-02', 35.00, 'yoga', 'Paris', 'attendance', '2025-11-03 00:00:00'),
('2025-11-03', 42.00, 'yoga', 'Paris', 'attendance', '2025-11-04 00:00:00'),
('2025-11-04', 38.00, 'yoga', 'Paris', 'attendance', '2025-11-05 00:00:00'),
('2025-11-05', 45.00, 'yoga', 'Paris', 'attendance', '2025-11-06 00:00:00'),
('2025-11-01', 8.00, NULL, 'London', 'events_count', '2025-11-02 00:00:00'),
('2025-11-02', 12.00, NULL, 'London', 'events_count', '2025-11-03 00:00:00'),
('2025-11-03', 6.00, NULL, 'London', 'events_count', '2025-11-04 00:00:00'),
('2025-11-04', 15.00, NULL, 'London', 'events_count', '2025-11-05 00:00:00'),
('2025-11-05', 10.00, NULL, 'London', 'events_count', '2025-11-06 00:00:00'),
('2025-11-06', 48.00, 'cooking', 'London', 'attendance', '2025-11-07 00:00:00'),
('2025-11-07', 56.00, 'cooking', 'London', 'attendance', '2025-11-08 00:00:00'),
('2025-11-08', 42.00, 'cooking', 'London', 'attendance', '2025-11-09 00:00:00'),
('2025-11-09', 65.00, 'cooking', 'London', 'attendance', '2025-11-10 00:00:00'),
('2025-11-10', 58.00, 'cooking', 'London', 'attendance', '2025-11-11 00:00:00');

-- =============================================================================
-- 8. INTEREST TAXONOMY - hobbies/categories
-- Schema: interest_id (PK), parent_id, level, is_active, created_at, updated_at
-- =============================================================================
INSERT INTO interest_taxonomy (interest_id, parent_id, level, is_active, created_at, updated_at) VALUES
('lifestyle', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('arts', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('sports', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('wellness', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('entertainment', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('education', NULL, 0, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('cooking', 'lifestyle', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('gardening', 'lifestyle', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('crafts', 'lifestyle', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('travel', 'lifestyle', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('photography', 'arts', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('painting', 'arts', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('music', 'arts', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('dancing', 'arts', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('hiking', 'sports', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('fitness', 'sports', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('yoga', 'wellness', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('gaming', 'entertainment', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('tech', 'education', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('languages', 'education', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00'),
('reading', 'education', 1, true, '2025-01-01 00:00:00', '2025-01-01 00:00:00');

-- =============================================================================
-- 9. UI STRINGS - for translation
-- Schema: key (PK), default_text, context, updated_at
-- =============================================================================
INSERT INTO ui_strings (key, default_text, context, updated_at) VALUES
('welcome.title', 'Welcome to Kumele', 'Home page greeting', '2025-01-01 00:00:00'),
('welcome.subtitle', 'Discover events and connect with people', 'Home page subtext', '2025-01-01 00:00:00'),
('nav.home', 'Home', 'Navigation menu', '2025-01-01 00:00:00'),
('nav.events', 'Events', 'Navigation menu', '2025-01-01 00:00:00'),
('nav.profile', 'Profile', 'Navigation menu', '2025-01-01 00:00:00'),
('nav.settings', 'Settings', 'Navigation menu', '2025-01-01 00:00:00'),
('event.create', 'Create Event', 'Event creation button', '2025-01-01 00:00:00'),
('event.join', 'Join Event', 'Event RSVP button', '2025-01-01 00:00:00'),
('event.cancel', 'Cancel', 'Cancel action button', '2025-01-01 00:00:00'),
('event.details', 'Event Details', 'Event page header', '2025-01-01 00:00:00'),
('rating.submit', 'Submit Rating', 'Rating form button', '2025-01-01 00:00:00'),
('rating.placeholder', 'Share your experience...', 'Rating comment placeholder', '2025-01-01 00:00:00'),
('error.generic', 'Something went wrong', 'Generic error message', '2025-01-01 00:00:00'),
('error.network', 'Network error. Please try again.', 'Network error message', '2025-01-01 00:00:00'),
('success.saved', 'Successfully saved!', 'Success message', '2025-01-01 00:00:00'),
('profile.edit', 'Edit Profile', 'Profile edit button', '2025-01-01 00:00:00'),
('profile.logout', 'Logout', 'Logout button', '2025-01-01 00:00:00'),
('search.placeholder', 'Search events...', 'Search input placeholder', '2025-01-01 00:00:00'),
('filter.category', 'Category', 'Filter label', '2025-01-01 00:00:00'),
('filter.location', 'Location', 'Filter label', '2025-01-01 00:00:00');

-- =============================================================================
-- 10. HOST RATING AGGREGATES - computed summary for hosts
-- Schema: host_id (PK), overall_score, overall_score_5, reviews_count, avg_*, badges, last_calculated
-- =============================================================================
INSERT INTO host_rating_aggregates (host_id, overall_score, overall_score_5, reviews_count, avg_communication, avg_respect, avg_professionalism, avg_atmosphere, avg_value_for_money, event_completion_ratio, attendance_follow_through, repeat_attendee_ratio, badges, last_calculated) VALUES
(1, 92.50, 4.63, 15, 4.75, 4.80, 4.60, 4.70, 4.50, 1.0000, 0.9500, 0.3500, '["top_rated", "veteran_host"]', '2026-01-05 00:00:00'),
(2, 88.00, 4.40, 12, 4.50, 4.60, 4.40, 4.50, 4.30, 0.9500, 0.9000, 0.3000, '["rising_star"]', '2026-01-05 00:00:00'),
(3, 85.50, 4.28, 10, 4.40, 4.50, 4.30, 4.40, 4.20, 0.9000, 0.8800, 0.2500, '[]', '2026-01-05 00:00:00'),
(4, 90.00, 4.50, 14, 4.60, 4.70, 4.50, 4.55, 4.40, 0.9800, 0.9200, 0.3200, '["top_rated"]', '2026-01-05 00:00:00'),
(5, 87.00, 4.35, 11, 4.45, 4.55, 4.35, 4.45, 4.25, 0.9200, 0.8900, 0.2800, '[]', '2026-01-05 00:00:00');

-- =============================================================================
-- 11. PRICING HISTORY - for sklearn regression training
-- Schema: event_id, price, turnout, host_score, city, category, capacity, event_date, revenue
-- =============================================================================
INSERT INTO pricing_history (event_id, price, turnout, host_score, city, category, capacity, event_date, revenue) VALUES
(1, 25.00, 45, 4.5, 'London', 'outdoor', 50, '2025-06-20', 1125.00),
(2, 35.00, 28, 4.2, 'New York', 'workshop', 30, '2025-07-15', 980.00),
(3, 15.00, 80, 4.8, 'Paris', 'social', 100, '2025-08-10', 1200.00),
(4, 50.00, 20, 4.0, 'Tokyo', 'fitness', 25, '2025-05-25', 1000.00),
(5, 30.00, 35, 4.3, 'Sydney', 'outdoor', 40, '2025-09-05', 1050.00),
(1, 28.00, 48, 4.5, 'London', 'outdoor', 50, '2025-07-20', 1344.00),
(2, 32.00, 30, 4.2, 'New York', 'workshop', 30, '2025-08-15', 960.00),
(3, 18.00, 75, 4.8, 'Paris', 'social', 100, '2025-09-10', 1350.00),
(4, 45.00, 22, 4.0, 'Tokyo', 'fitness', 25, '2025-06-25', 990.00),
(5, 35.00, 32, 4.3, 'Sydney', 'outdoor', 40, '2025-10-05', 1120.00),
(1, 30.00, 42, 4.5, 'London', 'outdoor', 50, '2025-08-20', 1260.00),
(2, 38.00, 26, 4.2, 'New York', 'workshop', 30, '2025-09-15', 988.00),
(3, 20.00, 70, 4.8, 'Paris', 'social', 100, '2025-10-10', 1400.00),
(4, 55.00, 18, 4.0, 'Tokyo', 'fitness', 25, '2025-07-25', 990.00),
(5, 32.00, 38, 4.3, 'Sydney', 'outdoor', 40, '2025-11-05', 1216.00);

-- =============================================================================
-- 12. KNOWLEDGE DOCUMENTS - for chatbot RAG
-- Schema: id (UUID), title, content, category, language, is_active, created_at
-- =============================================================================
INSERT INTO knowledge_documents (id, title, content, category, language, is_active, created_at) VALUES
('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'How to Create an Event', 'To create an event, navigate to the Events page and click "Create New Event". Fill in the event details including title, description, date, location, and capacity. You can set ticket prices and add images to make your event more attractive.', 'faq', 'en', true, '2025-01-01 00:00:00'),
('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'Booking and Payments', 'To book an event, click the "Join Event" button on any event page. You will be directed to a secure payment page. We accept all major credit cards. Your booking is confirmed once payment is processed.', 'faq', 'en', true, '2025-01-01 00:00:00'),
('c0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'Cancellation Policy', 'Cancellations made more than 48 hours before the event receive a full refund. Cancellations within 48 hours may receive a partial refund at the host discretion. No-shows are not eligible for refunds.', 'policy', 'en', true, '2025-01-01 00:00:00'),
('d0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14', 'Host Guidelines', 'As a host, you are responsible for event safety and communication. Respond to attendee questions within 24 hours. Provide accurate event descriptions and update attendees of any changes promptly.', 'policy', 'en', true, '2025-01-01 00:00:00'),
('e0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15', 'Getting Started Guide', 'Welcome to Kumele! Start by creating your profile and selecting your interests. Browse events in your area or create your own. Connect with like-minded people and build your community.', 'help', 'en', true, '2025-01-01 00:00:00');

-- =============================================================================
-- 13. INTEREST TRANSLATIONS - multilingual taxonomy labels
-- Schema: interest_id (FK), language_code, label, description
-- =============================================================================
INSERT INTO interest_translations (interest_id, language_code, label, description) VALUES
('outdoor', 'en', 'Outdoor Activities', 'Activities in nature and outdoors'),
('outdoor', 'fr', 'Activités de plein air', 'Activités dans la nature'),
('outdoor', 'ar', 'أنشطة خارجية', 'أنشطة في الهواء الطلق'),
('fitness', 'en', 'Fitness & Sports', 'Physical activities and sports'),
('fitness', 'fr', 'Fitness et Sports', 'Activités physiques et sports'),
('fitness', 'ar', 'اللياقة والرياضة', 'الأنشطة البدنية والرياضية'),
('social', 'en', 'Social Events', 'Meetups and social gatherings'),
('social', 'fr', 'Événements sociaux', 'Rencontres et rassemblements'),
('social', 'ar', 'فعاليات اجتماعية', 'لقاءات وتجمعات اجتماعية'),
('education', 'en', 'Education & Learning', 'Workshops and learning events'),
('education', 'fr', 'Éducation et apprentissage', 'Ateliers et événements éducatifs'),
('education', 'ar', 'التعليم والتعلم', 'ورش عمل وفعاليات تعليمية');

-- =============================================================================
-- 14. INTEREST METADATA - icons and display info
-- Schema: interest_id (FK), icon_key, color_token, display_order
-- =============================================================================
INSERT INTO interest_metadata (interest_id, icon_key, color_token, display_order) VALUES
('outdoor', '🏔️', 'green', 1),
('fitness', '💪', 'orange', 2),
('social', '🎉', 'purple', 3),
('education', '📚', 'blue', 4),
('hiking', '🥾', 'green', 10),
('yoga', '🧘', 'teal', 20),
('cooking', '👨‍🍳', 'red', 30),
('photography', '📷', 'gray', 40);

-- =============================================================================
-- DONE! Verify data loaded
-- =============================================================================
SELECT 'Data Loading Complete!' AS message;
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'event_ratings', COUNT(*) FROM event_ratings
UNION ALL SELECT 'user_interactions', COUNT(*) FROM user_interactions
UNION ALL SELECT 'user_activities', COUNT(*) FROM user_activities
UNION ALL SELECT 'reward_coupons', COUNT(*) FROM reward_coupons
UNION ALL SELECT 'timeseries_daily', COUNT(*) FROM timeseries_daily
UNION ALL SELECT 'interest_taxonomy', COUNT(*) FROM interest_taxonomy
UNION ALL SELECT 'ui_strings', COUNT(*) FROM ui_strings
UNION ALL SELECT 'host_rating_aggregates', COUNT(*) FROM host_rating_aggregates
UNION ALL SELECT 'pricing_history', COUNT(*) FROM pricing_history
UNION ALL SELECT 'knowledge_documents', COUNT(*) FROM knowledge_documents
UNION ALL SELECT 'interest_translations', COUNT(*) FROM interest_translations
UNION ALL SELECT 'interest_metadata', COUNT(*) FROM interest_metadata;
