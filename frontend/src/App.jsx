import { useEffect, useState } from "react"

const API = "http://localhost:8000/api"
const initialAssignment = { user_id: "", space_id: "", seat_id: "", starts_on: "", ends_on: "" }

function App() {
  const [spaces, setSpaces] = useState([])
  const [users, setUsers] = useState([])
  const [seats, setSeats] = useState([])
  const [assignments, setAssignments] = useState([])
  const [space, setSpace] = useState({ name: "", uses_seats: true, study_room: false })
  const [user, setUser] = useState({ name: "", identifier: "", student_id: "", gender: "" })
  const [editUser, setEditUser] = useState(null)
  const [seat, setSeat] = useState({ space_id: "", number: "" })
  const [assignment, setAssignment] = useState(initialAssignment)
  const [moveId, setMoveId] = useState("")
  const [endId, setEndId] = useState("")
  const [endDate, setEndDate] = useState("")
  const [periods, setPeriods] = useState([])
  const [slots, setSlots] = useState([])
  const [period, setPeriod] = useState({ space_id: "", name: "", starts_on: "", ends_on: "" })
  const [slot, setSlot] = useState({ period_id: "", name: "", starts_at: "", ends_at: "" })
  const [message, setMessage] = useState("")

  async function request(path, options) {
    let response
    try {
      response = await fetch(API + path, options)
    } catch {
      throw new Error(`API 연결 실패 (${path}): 서버가 실행 중인지 확인하세요.`)
    }
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = typeof data?.detail === "string" ? `: ${data.detail}` : ""
      throw new Error(`API 오류 (${path}, HTTP ${response.status})${detail}`)
    }
    if (data === null) throw new Error(`API 응답을 읽을 수 없습니다 (${path}).`)
    return data
  }
  async function refresh() {
    const [a, b, c, d, p, t] = await Promise.all(["/spaces", "/users", "/seats", "/assignments", "/periods", "/time-slots"].map(path => request(path)))
    setSpaces(a); setUsers(b); setSeats(c); setAssignments(d); setPeriods(p); setSlots(t)
  }
  useEffect(() => {
    Promise.all(["/spaces", "/users", "/seats", "/assignments", "/periods", "/time-slots"].map(path => request(path)))
      .then(([a, b, c, d, p, t]) => { setSpaces(a); setUsers(b); setSeats(c); setAssignments(d); setPeriods(p); setSlots(t) })
      .catch(e => setMessage(e.message))
  }, [])
  async function submit(path, data, reset, method = "POST") {
    try {
      await request(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
      await refresh(); reset(); setMessage("저장했습니다.")
    } catch (error) { setMessage(error.message) }
  }
  const spaceName = id => spaces.find(s => s.id === id)?.name ?? id
  const userName = id => users.find(u => u.id === id)?.name ?? id
  const seatName = id => id == null ? "공간 단위" : (seats.find(s => s.id === id)?.number ?? id)
  const assignmentData = { ...assignment, user_id: Number(assignment.user_id), space_id: Number(assignment.space_id), seat_id: assignment.seat_id ? Number(assignment.seat_id) : null, ends_on: assignment.ends_on || null }
  const selectedSpace = spaces.find(s => s.id === Number(assignment.space_id))

  return <div style={{ padding: "20px" }}>
    <h1>공간 활용 관리</h1>
    {message && <p role="status">{message}</p>}
    <h2>공간 추가</h2>
    <form onSubmit={e => { e.preventDefault(); submit("/spaces", space, () => setSpace({ name: "", uses_seats: true, study_room: false })) }}>
      <input aria-label="공간 이름" placeholder="공간 이름" required value={space.name} onChange={e => setSpace({ ...space, name: e.target.value })} />
      <label><input type="checkbox" checked={space.uses_seats} onChange={e => setSpace({ ...space, uses_seats: e.target.checked })} />좌석 사용</label>
      <label><input type="checkbox" checked={space.study_room} onChange={e => setSpace({ ...space, study_room: e.target.checked })} />자습실</label>
      <button>추가</button>
    </form>
    <ul>{spaces.map(s => <li key={s.id}>{s.name} ({s.uses_seats ? "좌석 사용" : "좌석 없음"}{s.study_room ? ", 자습실" : ""})</li>)}</ul>
    <h2>운영 기간</h2>
    <form onSubmit={e => { e.preventDefault(); submit('/periods', { ...period, space_id: Number(period.space_id) }, () => setPeriod({ space_id: "", name: "", starts_on: "", ends_on: "" })) }}>
      <select aria-label="운영 기간 공간" required value={period.space_id} onChange={e => setPeriod({ ...period, space_id: e.target.value })}><option value="">공간 선택</option>{spaces.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <input aria-label="운영 기간 이름" placeholder="기간 이름" required value={period.name} onChange={e => setPeriod({ ...period, name: e.target.value })} />
      <label>시작일 <input type="date" required value={period.starts_on} onChange={e => setPeriod({ ...period, starts_on: e.target.value })} /></label>
      <label>종료일 (미포함) <input type="date" required value={period.ends_on} onChange={e => setPeriod({ ...period, ends_on: e.target.value })} /></label><button>추가</button>
    </form>
    <ul>{periods.map(p => <li key={p.id}>{spaceName(p.space_id)} / {p.name} / {p.starts_on} ~ {p.ends_on} (종료일 미포함)</li>)}</ul>
    <h2>주간 반복 시간대</h2>
    <form onSubmit={e => { e.preventDefault(); submit('/time-slots', { ...slot, period_id: Number(slot.period_id) }, () => setSlot({ period_id: "", name: "", starts_at: "", ends_at: "" })) }}>
      <select aria-label="시간대 운영 기간" required value={slot.period_id} onChange={e => setSlot({ ...slot, period_id: e.target.value })}><option value="">기간 선택</option>{periods.map(p => <option key={p.id} value={p.id}>{spaceName(p.space_id)} / {p.name}</option>)}</select>
      <input aria-label="시간대 이름" placeholder="시간대 이름" required value={slot.name} onChange={e => setSlot({ ...slot, name: e.target.value })} />
      <label>시작 <input type="time" required value={slot.starts_at} onChange={e => setSlot({ ...slot, starts_at: e.target.value })} /></label><label>종료 <input type="time" required value={slot.ends_at} onChange={e => setSlot({ ...slot, ends_at: e.target.value })} /></label><button>추가</button>
    </form>
    <ul>{slots.map(t => <li key={t.id}>{periods.find(p => p.id === t.period_id)?.name} / {t.name} / {t.starts_at} ~ {t.ends_at}</li>)}</ul>
    <h2>이용자 {editUser ? "수정" : "등록"}</h2>
    <form onSubmit={e => { e.preventDefault(); submit(editUser ? `/users/${editUser}` : "/users", user, () => { setUser({ name: "", identifier: "", student_id: "", gender: "" }); setEditUser(null) }, editUser ? "PUT" : "POST") }}>
      {[['name', '이름'], ['identifier', '식별 정보'], ['student_id', '학번'], ['gender', '성별']].map(([key, label]) => <input key={key} aria-label={label} placeholder={label} required={key === 'name'} value={user[key] || ""} onChange={e => setUser({ ...user, [key]: e.target.value })} />)}
      <button>저장</button>{editUser && <button type="button" onClick={() => { setEditUser(null); setUser({ name: "", identifier: "", student_id: "", gender: "" }) }}>취소</button>}
    </form>
    <ul>{users.map(u => <li key={u.id}>{u.name} {u.identifier} {u.student_id} {u.gender} <button onClick={() => { setEditUser(u.id); setUser(u) }}>수정</button></li>)}</ul>
    <h2>좌석 추가·사용 중지</h2>
    <form onSubmit={e => { e.preventDefault(); submit('/seats', { ...seat, space_id: Number(seat.space_id) }, () => setSeat({ space_id: "", number: "" })) }}>
      <select aria-label="좌석 공간" required value={seat.space_id} onChange={e => setSeat({ ...seat, space_id: e.target.value })}><option value="">공간 선택</option>{spaces.filter(s => s.uses_seats).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <input aria-label="좌석번호" placeholder="좌석번호" required value={seat.number} onChange={e => setSeat({ ...seat, number: e.target.value })} /><button>추가</button>
    </form>
    <ul>{seats.map(s => <li key={s.id}>{spaceName(s.space_id)} / {s.number} / {s.active ? "사용 중" : "사용 중지"} {s.active ? <button onClick={() => submit(`/seats/${s.id}/deactivate`, {}, () => {})}>사용 중지</button> : null}</li>)}</ul>
    <h2>{moveId ? '배정 이동' : '배정 추가'}</h2>
    <form onSubmit={e => { e.preventDefault(); const move = { space_id: assignmentData.space_id, seat_id: assignmentData.seat_id, starts_on: assignmentData.starts_on, ends_on: assignmentData.ends_on }; submit(moveId ? `/assignments/${moveId}/move` : '/assignments', moveId ? move : assignmentData, () => { setAssignment(initialAssignment); setMoveId("") }) }}>
      {!moveId && <select aria-label="배정 이용자" required value={assignment.user_id} onChange={e => setAssignment({ ...assignment, user_id: e.target.value })}><option value="">이용자 선택</option>{users.map(u => <option key={u.id} value={u.id}>{u.name} {u.identifier}</option>)}</select>}
      <select aria-label="배정 공간" required value={assignment.space_id} onChange={e => setAssignment({ ...assignment, space_id: e.target.value, seat_id: "" })}><option value="">공간 선택</option>{spaces.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      {selectedSpace?.uses_seats ? <select aria-label="배정 좌석" required value={assignment.seat_id} onChange={e => setAssignment({ ...assignment, seat_id: e.target.value })}><option value="">좌석 선택</option>{seats.filter(s => s.space_id === selectedSpace.id && s.active).map(s => <option key={s.id} value={s.id}>{s.number}</option>)}</select> : null}
      <label>시작일 <input type="date" required value={assignment.starts_on} onChange={e => setAssignment({ ...assignment, starts_on: e.target.value })} /></label>
      <label>종료일 (미포함) <input type="date" value={assignment.ends_on} onChange={e => setAssignment({ ...assignment, ends_on: e.target.value })} /></label><button>저장</button>
      {moveId && <button type="button" onClick={() => { setMoveId(""); setAssignment(initialAssignment) }}>이동 취소</button>}
    </form>
    <h2>배정 이력</h2>
    <table border="1" cellPadding="8"><thead><tr><th>이용자</th><th>공간</th><th>좌석</th><th>시작일</th><th>종료일 (미포함)</th><th>관리</th></tr></thead><tbody>{assignments.map(a => <tr key={a.id}><td>{userName(a.user_id)}</td><td>{spaceName(a.space_id)}</td><td>{seatName(a.seat_id)}</td><td>{a.starts_on}</td><td>{a.ends_on || '미정'}</td><td><button onClick={() => { setMoveId(a.id); setAssignment(initialAssignment) }}>이동</button> <button onClick={() => { setEndId(a.id); setEndDate("") }}>종료</button></td></tr>)}</tbody></table>
    {endId && <form onSubmit={e => { e.preventDefault(); submit(`/assignments/${endId}/end`, { ends_on: endDate }, () => setEndId("")) }}><label>종료일 (미포함) <input type="date" required value={endDate} onChange={e => setEndDate(e.target.value)} /></label><button>배정 종료</button><button type="button" onClick={() => setEndId("")}>취소</button></form>}
  </div>
}
export default App
