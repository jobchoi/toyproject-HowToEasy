import { useCallback, useEffect, useState } from "react"
import "./App.css"

const API = "http://localhost:8000/api"
const initialAssignment = { user_id: "", space_id: "", seat_id: "", starts_on: "", ends_on: "" }

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("spaceToken") || "")
  const [account, setAccount] = useState(null)
  const [credentials, setCredentials] = useState({ username: "", password: "" })
  const [newAccount, setNewAccount] = useState({ username: "", password: "", role: "staff" })
  const [backups, setBackups] = useState([])
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
  const [reportPeriod, setReportPeriod] = useState("")
  const [reportDate, setReportDate] = useState("")
  const [reportResult, setReportResult] = useState(null)
  const [responsePeriod, setResponsePeriod] = useState("")
  const [responses, setResponses] = useState([])
  const [response, setResponse] = useState({ user_id: '', slot_id: '', weekday: '0', status: '', reason: '' })
  const [message, setMessage] = useState("")

  const request = useCallback(async (path, options) => {
    const requestToken = token
    options?.signal?.throwIfAborted()
    let response
    try {
      response = await fetch(API + path, { ...options, headers: { ...options?.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) } })
    } catch (error) {
      if (options?.signal?.aborted) throw error
      throw new Error(`API 연결 실패 (${path}): 서버가 실행 중인지 확인하세요.`, { cause: error })
    }
    const data = await response.json().catch(() => null)
    options?.signal?.throwIfAborted()
    if (!response.ok) {
      if (response.status === 401 && path !== "/auth/login" && requestToken === (sessionStorage.getItem("spaceToken") || "")) { sessionStorage.removeItem("spaceToken"); setToken(""); setAccount(null) }
      const detail = typeof data?.detail === "string" ? `: ${data.detail}` : ""
      throw new Error(`API 오류 (${path}, HTTP ${response.status})${detail}`)
    }
    if (data === null) throw new Error(`API 응답을 읽을 수 없습니다 (${path}).`)
    return data
  }, [token])
  const refresh = useCallback(async () => {
    const [a, b, c, d, p, t, r] = await Promise.all(["/spaces", "/users", "/seats", "/assignments", "/periods", "/time-slots", "/weekly-responses"].map(path => request(path)))
    setSpaces(a); setUsers(b); setSeats(c); setAssignments(d); setPeriods(p); setSlots(t); setResponses(r)
  }, [request])
  useEffect(() => {
    if (!token) return
    Promise.resolve().then(() => request("/auth/me")).then(setAccount).catch(e => setMessage(e.message))
  }, [token, request])
  useEffect(() => {
    if (!account) return
    Promise.resolve().then(() => refresh()).catch(e => setMessage(e.message))
    if (account.role === "admin") Promise.resolve().then(() => request("/backups")).then(setBackups).catch(e => setMessage(e.message))
  }, [account, refresh, request])
  async function login(e) {
    e.preventDefault()
    try {
      const result = await request("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(credentials) })
      sessionStorage.setItem("spaceToken", result.token); setToken(result.token); setCredentials({ username: "", password: "" }); setMessage("")
    } catch (error) { setMessage(error.message) }
  }
  async function logout() {
    try { await request("/auth/logout", { method: "POST" }) } catch { /* clear local session regardless */ }
    sessionStorage.removeItem("spaceToken"); setToken(""); setAccount(null)
  }
  async function manageBackup(name) {
    if (name && !window.confirm("선택한 백업으로 복구합니다. 현재 DB는 자동 백업되며 다시 로그인해야 합니다. 계속할까요?")) return
    try {
      const result = await request(name ? "/backups/restore" : "/backups", { method: "POST", headers: { "Content-Type": "application/json" }, body: name ? JSON.stringify({ name }) : undefined })
      if (name) { sessionStorage.removeItem("spaceToken"); setToken(""); setAccount(null); setMessage(`복구했습니다. 복구 전 백업: ${result.pre_restore_backup}. 다시 로그인하세요.`) }
      else { setBackups(await request("/backups")); setMessage(`백업 생성: ${result.name}`) }
    } catch (error) { setMessage(error.message) }
  }
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

  const chosenPeriod = periods.find(p => p.id === Number(reportPeriod))
  const reportValid = chosenPeriod && reportDate >= chosenPeriod.starts_on && reportDate < chosenPeriod.ends_on
  // Hide results immediately when selection, session, or saved data changes.
  const reportData = token && reportValid && reportResult?.token === token
    && reportResult.period === reportPeriod && reportResult.date === reportDate
    && reportResult.assignments === assignments && reportResult.responses === responses
    ? reportResult.data : null
  useEffect(() => {
    const controller = new AbortController()
    if (token && reportValid) Promise.resolve().then(() => request(`/reports?period_id=${reportPeriod}&on=${reportDate}`, { signal: controller.signal }))
      .then(data => { if (!controller.signal.aborted) setReportResult({ token, period: reportPeriod, date: reportDate, assignments, responses, data }) })
      .catch(error => { if (!controller.signal.aborted) setMessage(error.message) })
    return () => controller.abort()
  }, [token, reportPeriod, reportDate, reportValid, assignments, responses, request])
  const weekday = reportValid ? (new Date(`${reportDate}T00:00:00`).getDay() + 6) % 7 : -1
  const reportAssignments = reportData?.assignments ?? []
  const reportSlots = reportData?.slots ?? []
  if (!token || !account) return <div style={{ padding: "20px" }}><h1>담당자 로그인</h1>{message && <p role="status">{message}</p>}<form onSubmit={login}>
    <input aria-label="아이디" autoComplete="username" required value={credentials.username} onChange={e => setCredentials({ ...credentials, username: e.target.value })} />
    <input aria-label="비밀번호" type="password" autoComplete="current-password" required value={credentials.password} onChange={e => setCredentials({ ...credentials, password: e.target.value })} /><button>로그인</button></form></div>
  return <div style={{ padding: "20px" }}>
    <h1>공간 활용 관리</h1>
    <p className="edit-content">{account.username} ({account.role === "admin" ? "운영자" : "담당자"}) <button onClick={logout}>로그아웃</button></p>
    {message && <p role="status">{message}</p>}
    {account.role === "admin" && <section className="edit-content"><h2>담당자 계정 생성</h2><form onSubmit={async e => { e.preventDefault(); try { await request("/auth/accounts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newAccount) }); setNewAccount({ username: "", password: "", role: "staff" }); setMessage("계정을 생성했습니다.") } catch (error) { setMessage(error.message) } }}>
      <input aria-label="새 아이디" placeholder="아이디" required value={newAccount.username} onChange={e => setNewAccount({ ...newAccount, username: e.target.value })} /><input aria-label="새 비밀번호" placeholder="비밀번호 (8자 이상)" type="password" minLength="8" required value={newAccount.password} onChange={e => setNewAccount({ ...newAccount, password: e.target.value })} /><select aria-label="계정 역할" value={newAccount.role} onChange={e => setNewAccount({ ...newAccount, role: e.target.value })}><option value="staff">담당자</option><option value="admin">운영자</option></select><button>계정 생성</button></form>
      <h2>백업·복구</h2><button onClick={() => manageBackup()}>현재 DB 백업</button><ul>{backups.map(name => <li key={name}>{name} <button onClick={() => manageBackup(name)}>복구</button></li>)}</ul></section>}
    <section id="reports" className="report-controls"><h2>운영표·좌석표 조회</h2>
      <select aria-label="표 운영 기간" value={reportPeriod} onChange={e => setReportPeriod(e.target.value)}><option value="">공간 / 기간 선택</option>{periods.map(p => <option key={p.id} value={p.id}>{spaceName(p.space_id)} / {p.name}</option>)}</select>
      <input aria-label="표 기준 날짜" type="date" value={reportDate} onChange={e => setReportDate(e.target.value)} />
      <button type="button" disabled={!reportValid || !reportData} onClick={() => window.print()}>인쇄</button>
      {reportDate && chosenPeriod && !reportValid && <p>운영 기간 안의 날짜를 선택하세요 (종료일 미포함).</p>}
    </section>
    {reportValid && reportData && <section className="print-report"><h2>{spaceName(chosenPeriod.space_id)} / {chosenPeriod.name} / {reportDate}</h2>
      <h3>운영표 ({['월','화','수','목','금','토','일'][weekday]}요일 주간 반복 사전 응답)</h3>
      <table border="1" cellPadding="6"><thead><tr><th>이용자</th>{reportSlots.map(t => <th key={t.id}>{t.name} ({t.starts_at}~{t.ends_at})</th>)}</tr></thead><tbody>{reportAssignments.map(a => <tr key={a.id}><td>{userName(a.user_id)}</td>{reportSlots.map(t => { const r = a.responses.find(x => x.slot_id === t.id); return <td key={t.id}>{r?.status ? (r.status === 'attending' ? '참여 예정' : '불참 예정') : '미응답'}{r?.reason ? ` (${r.reason})` : ''}</td> })}</tr>)}</tbody></table>
      <h3>좌석표</h3><table border="1" cellPadding="6"><thead><tr><th>좌석</th><th>이용자</th></tr></thead><tbody>{spaces.find(s => s.id === chosenPeriod.space_id)?.uses_seats
        ? reportData.seats.map(s => <tr key={s.id}><td>{s.number}{!s.active && " (사용 중지)"}</td><td>{s.assignment?.user_name ?? "빈 좌석"}</td></tr>)
        : reportAssignments.map(a => <tr key={a.id}><td>공간 단위</td><td>{a.user_name}</td></tr>)}</tbody></table>
    </section>}
    <nav className="edit-content" aria-label="작업 순서"><a href="#spaces">공간</a> → <a href="#periods">운영 기간</a> → <a href="#slots">시간대</a> → <a href="#assignments">좌석·배정</a> → <a href="#responses">사전 응답</a> → <a href="#reports">표 조회</a></nav>
    <div className="edit-content"><h2 id="spaces">공간 추가</h2>
    <form onSubmit={e => { e.preventDefault(); submit("/spaces", space, () => setSpace({ name: "", uses_seats: true, study_room: false })) }}>
      <input aria-label="공간 이름" placeholder="공간 이름" required value={space.name} onChange={e => setSpace({ ...space, name: e.target.value })} />
      <label><input type="checkbox" checked={space.uses_seats} onChange={e => setSpace({ ...space, uses_seats: e.target.checked })} />좌석 사용</label>
      <label><input type="checkbox" checked={space.study_room} onChange={e => setSpace({ ...space, study_room: e.target.checked })} />자습실</label>
      <button>추가</button>
    </form>
    <ul>{spaces.map(s => <li key={s.id}>{s.name} ({s.uses_seats ? "좌석 사용" : "좌석 없음"}{s.study_room ? ", 자습실" : ""})</li>)}</ul>
    <h2 id="periods">운영 기간</h2>
    <form onSubmit={e => { e.preventDefault(); submit('/periods', { ...period, space_id: Number(period.space_id) }, () => setPeriod({ space_id: "", name: "", starts_on: "", ends_on: "" })) }}>
      <select aria-label="운영 기간 공간" required value={period.space_id} onChange={e => setPeriod({ ...period, space_id: e.target.value })}><option value="">공간 선택</option>{spaces.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      <input aria-label="운영 기간 이름" placeholder="기간 이름" required value={period.name} onChange={e => setPeriod({ ...period, name: e.target.value })} />
      <label>시작일 <input type="date" required value={period.starts_on} onChange={e => setPeriod({ ...period, starts_on: e.target.value })} /></label>
      <label>종료일 (미포함) <input type="date" required value={period.ends_on} onChange={e => setPeriod({ ...period, ends_on: e.target.value })} /></label><button>추가</button>
    </form>
    <ul>{periods.map(p => <li key={p.id}>{spaceName(p.space_id)} / {p.name} / {p.starts_on} ~ {p.ends_on} (종료일 미포함)</li>)}</ul>
    <h2 id="slots">주간 반복 시간대</h2>
    <form onSubmit={e => { e.preventDefault(); submit('/time-slots', { ...slot, period_id: Number(slot.period_id) }, () => setSlot({ period_id: "", name: "", starts_at: "", ends_at: "" })) }}>
      <select aria-label="시간대 운영 기간" required value={slot.period_id} onChange={e => setSlot({ ...slot, period_id: e.target.value })}><option value="">기간 선택</option>{periods.map(p => <option key={p.id} value={p.id}>{spaceName(p.space_id)} / {p.name}</option>)}</select>
      <input aria-label="시간대 이름" placeholder="시간대 이름" required value={slot.name} onChange={e => setSlot({ ...slot, name: e.target.value })} />
      <label>시작 <input type="time" required value={slot.starts_at} onChange={e => setSlot({ ...slot, starts_at: e.target.value })} /></label><label>종료 <input type="time" required value={slot.ends_at} onChange={e => setSlot({ ...slot, ends_at: e.target.value })} /></label><button>추가</button>
    </form>
    <ul>{slots.map(t => <li key={t.id}>{periods.find(p => p.id === t.period_id)?.name} / {t.name} / {t.starts_at} ~ {t.ends_at}</li>)}</ul>
    <h2 id="responses">주간 사전 응답</h2>
    <p>선택한 운영 기간의 매주 반복 일정입니다. 빈칸은 미응답입니다. 이용자·기간·시간대·요일을 선택하고 저장하세요. 미응답 저장은 기존 응답을 지웁니다.</p>
    <form onSubmit={e => { e.preventDefault(); submit('/weekly-responses', { ...response, user_id: Number(response.user_id), slot_id: Number(response.slot_id), weekday: Number(response.weekday), status: response.status || null }, () => {}, 'PUT') }}>
      <select aria-label="응답 이용자" required value={response.user_id} onChange={e => setResponse({ ...response, user_id: e.target.value })}><option value="">이용자 선택</option>{users.map(u => <option key={u.id} value={u.id}>{u.name} {u.identifier}</option>)}</select>
      <select aria-label="응답 운영 기간" required value={responsePeriod} onChange={e => { setResponsePeriod(e.target.value); setResponse({ ...response, slot_id: "" }) }}><option value="">공간 / 기간 선택</option>{periods.map(p => <option key={p.id} value={p.id}>{spaceName(p.space_id)} / {p.name}</option>)}</select>
      <select aria-label="응답 시간대" required value={response.slot_id} onChange={e => setResponse({ ...response, slot_id: e.target.value })}><option value="">시간대 선택</option>{slots.filter(t => t.period_id === Number(responsePeriod)).map(t => <option key={t.id} value={t.id}>{periods.find(p => p.id === t.period_id)?.name} / {t.name}</option>)}</select>
      <select aria-label="응답 요일" value={response.weekday} onChange={e => setResponse({ ...response, weekday: e.target.value })}>{['월','화','수','목','금','토','일'].map((d, i) => <option key={d} value={i}>{d}</option>)}</select>
      <select aria-label="응답 상태" value={response.status} onChange={e => setResponse({ ...response, status: e.target.value })}><option value="">미응답</option><option value="attending">참여 예정</option><option value="absent">불참 예정</option></select>
      <input aria-label="응답 사유" placeholder="사유 (선택)" value={response.reason} onChange={e => setResponse({ ...response, reason: e.target.value })} /><button>응답 저장</button>
    </form>
    <ul>{responses.map(r => <li key={`${r.user_id}-${r.slot_id}-${r.weekday}`}>{userName(r.user_id)} / {slots.find(t => t.id === r.slot_id)?.name} / {['월','화','수','목','금','토','일'][r.weekday]} / {r.status === 'attending' ? '참여 예정' : '불참 예정'} {r.reason} <button type="button" onClick={() => { setResponsePeriod(String(slots.find(t => t.id === r.slot_id)?.period_id ?? "")); setResponse({ ...r, user_id: String(r.user_id), slot_id: String(r.slot_id), weekday: String(r.weekday), reason: r.reason || "" }) }}>수정</button></li>)}</ul>
    <h2>이용자 {editUser ? "수정" : "등록"}</h2>
    <form onSubmit={e => { e.preventDefault(); submit(editUser ? `/users/${editUser}` : "/users", user, () => { setUser({ name: "", identifier: "", student_id: "", gender: "" }); setEditUser(null) }, editUser ? "PUT" : "POST") }}>
      {[['name', '이름'], ['identifier', '식별 정보'], ['student_id', '학번'], ['gender', '성별']].map(([key, label]) => <input key={key} aria-label={label} placeholder={label} required={key === 'name'} value={user[key] || ""} onChange={e => setUser({ ...user, [key]: e.target.value })} />)}
      <button>저장</button>{editUser && <button type="button" onClick={() => { setEditUser(null); setUser({ name: "", identifier: "", student_id: "", gender: "" }) }}>취소</button>}
    </form>
    <ul>{users.map(u => <li key={u.id}>{u.name} {u.identifier} {u.student_id} {u.gender} <button onClick={() => { setEditUser(u.id); setUser(u) }}>수정</button></li>)}</ul>
    <h2 id="assignments">좌석 추가·사용 중지</h2>
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
  </div>
}
export default App
