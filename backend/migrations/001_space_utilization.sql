-- 앱 시작 시 이력 관리와 함께 적용한다. 기존 students 테이블과 데이터는 변경하지 않는다.
-- 연결마다 PRAGMA foreign_keys = ON이 필요하다. 날짜는 YYYY-MM-DD, 경계는 [시작, 종료).
PRAGMA foreign_keys = ON;
BEGIN;
CREATE TABLE spaces (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    uses_seats INTEGER NOT NULL CHECK(uses_seats IN (0, 1)),
    study_room INTEGER NOT NULL DEFAULT 0 CHECK(study_room IN (0, 1))
);
CREATE TABLE operating_periods (
    id INTEGER PRIMARY KEY,
    space_id INTEGER NOT NULL REFERENCES spaces(id),
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    starts_on TEXT NOT NULL CHECK(date(starts_on) IS NOT NULL AND date(starts_on) = starts_on),
    ends_on TEXT NOT NULL CHECK(date(ends_on) IS NOT NULL AND date(ends_on) = ends_on AND ends_on > starts_on)
);
CREATE TABLE time_slots (
    id INTEGER PRIMARY KEY,
    period_id INTEGER NOT NULL REFERENCES operating_periods(id),
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    starts_at TEXT NOT NULL CHECK(length(starts_at) = 5 AND time(starts_at) IS NOT NULL AND strftime('%H:%M', starts_at) = starts_at),
    ends_at TEXT NOT NULL CHECK(length(ends_at) = 5 AND time(ends_at) IS NOT NULL AND strftime('%H:%M', ends_at) = ends_at AND ends_at > starts_at),
    UNIQUE(period_id, name)
);
CREATE TABLE space_users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    identifier TEXT,
    student_id TEXT,
    gender TEXT
);
CREATE TABLE seats (
    id INTEGER PRIMARY KEY,
    space_id INTEGER NOT NULL REFERENCES spaces(id),
    number TEXT NOT NULL CHECK(length(trim(number)) > 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    UNIQUE(space_id, number)
);
CREATE TABLE assignments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES space_users(id),
    space_id INTEGER NOT NULL REFERENCES spaces(id),
    seat_id INTEGER REFERENCES seats(id),
    starts_on TEXT NOT NULL CHECK(date(starts_on) IS NOT NULL AND date(starts_on) = starts_on),
    ends_on TEXT CHECK(ends_on IS NULL OR (date(ends_on) IS NOT NULL AND date(ends_on) = ends_on AND ends_on > starts_on))
);
CREATE TRIGGER seats_insert_validate BEFORE INSERT ON seats BEGIN
    SELECT CASE WHEN (SELECT uses_seats FROM spaces WHERE id = NEW.space_id) != 1 THEN RAISE(ABORT, '좌석 없는 공간에는 좌석을 추가할 수 없습니다') END;
END;
CREATE TRIGGER seats_update_validate BEFORE UPDATE ON seats BEGIN
    SELECT CASE WHEN NEW.space_id != OLD.space_id OR NEW.number != OLD.number THEN RAISE(ABORT, '좌석 공간과 번호는 변경할 수 없습니다') END;
    SELECT CASE WHEN NEW.active = 0 AND OLD.active = 1 AND EXISTS (SELECT 1 FROM assignments WHERE seat_id = OLD.id AND (ends_on IS NULL OR ends_on > date('now'))) THEN RAISE(ABORT, '배정 중이거나 예정된 좌석은 사용 중지할 수 없습니다') END;
END;
CREATE TRIGGER spaces_update_validate BEFORE UPDATE OF uses_seats ON spaces WHEN NEW.uses_seats != OLD.uses_seats BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM seats WHERE space_id = OLD.id) OR EXISTS (SELECT 1 FROM assignments WHERE space_id = OLD.id) THEN RAISE(ABORT, '좌석 또는 배정이 있는 공간의 좌석 사용 여부는 변경할 수 없습니다') END;
END;
CREATE TRIGGER assignments_insert_validate BEFORE INSERT ON assignments BEGIN
    SELECT CASE WHEN (SELECT uses_seats FROM spaces WHERE id = NEW.space_id) = 1 AND NEW.seat_id IS NULL THEN RAISE(ABORT, '좌석을 선택해야 합니다') END;
    SELECT CASE WHEN (SELECT uses_seats FROM spaces WHERE id = NEW.space_id) = 0 AND NEW.seat_id IS NOT NULL THEN RAISE(ABORT, '좌석 없는 공간에는 좌석을 배정할 수 없습니다') END;
    SELECT CASE WHEN NEW.seat_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM seats WHERE id = NEW.seat_id AND space_id = NEW.space_id AND active = 1) THEN RAISE(ABORT, '해당 공간의 사용 중인 좌석을 선택해야 합니다') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM assignments a WHERE (a.user_id = NEW.user_id OR (NEW.seat_id IS NOT NULL AND a.seat_id = NEW.seat_id)) AND (a.ends_on IS NULL OR NEW.starts_on < a.ends_on) AND (NEW.ends_on IS NULL OR a.starts_on < NEW.ends_on)) THEN RAISE(ABORT, '이용자 또는 좌석의 배정 기간이 겹칩니다') END;
END;
CREATE TRIGGER assignments_update_validate BEFORE UPDATE ON assignments BEGIN
    SELECT CASE WHEN NEW.user_id != OLD.user_id OR NEW.space_id != OLD.space_id OR NEW.seat_id IS NOT OLD.seat_id OR NEW.starts_on != OLD.starts_on THEN RAISE(ABORT, '배정 변경은 기존 배정 종료 후 새로 생성해야 합니다') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM assignments a WHERE a.id != OLD.id AND (a.user_id = NEW.user_id OR (NEW.seat_id IS NOT NULL AND a.seat_id = NEW.seat_id)) AND (a.ends_on IS NULL OR NEW.starts_on < a.ends_on) AND (NEW.ends_on IS NULL OR a.starts_on < NEW.ends_on)) THEN RAISE(ABORT, '이용자 또는 좌석의 배정 기간이 겹칩니다') END;
END;
COMMIT;
