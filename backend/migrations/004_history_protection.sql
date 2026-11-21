-- 배정은 종료·이동으로 보존한다. REPLACE를 통한 이력 덮어쓰기도 거부한다.
CREATE TRIGGER assignments_delete_protect BEFORE DELETE ON assignments BEGIN
    SELECT RAISE(ABORT, '배정 이력은 삭제할 수 없습니다. 종료 또는 이동하세요');
END;
CREATE TRIGGER assignments_replace_protect BEFORE INSERT ON assignments
WHEN EXISTS (SELECT 1 FROM assignments WHERE id=NEW.id) BEGIN
    SELECT RAISE(ABORT, '기존 배정 이력을 덮어쓸 수 없습니다');
END;
CREATE TRIGGER seats_delete_protect BEFORE DELETE ON seats
WHEN EXISTS (SELECT 1 FROM assignments WHERE seat_id=OLD.id) BEGIN
    SELECT RAISE(ABORT, '배정 이력이 있는 좌석은 사용 중지하세요');
END;
