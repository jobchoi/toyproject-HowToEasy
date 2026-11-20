CREATE TABLE weekly_responses (
    user_id INTEGER NOT NULL REFERENCES space_users(id),
    slot_id INTEGER NOT NULL REFERENCES time_slots(id),
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
    status TEXT NOT NULL CHECK(status IN ('attending', 'absent')),
    reason TEXT,
    PRIMARY KEY(user_id, slot_id, weekday)
);
