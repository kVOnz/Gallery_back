CREATE DATABASE image_gallery;

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE images (
    image_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    title VARCHAR(255),
    file_path VARCHAR(512) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_images_user_id ON images(user_id);
CREATE INDEX idx_images_title ON images(title);
CREATE INDEX idx_images_uploaded_at ON images(uploaded_at);