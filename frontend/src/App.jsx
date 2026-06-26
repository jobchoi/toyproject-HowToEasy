import { useEffect, useState } from "react"

function App() {
  const [students, setStudents] = useState([])
  const [form, setForm] = useState({
    seat_number: "",
    student_id: "",
    name: "",
    gender: "남",
    room_type: "정독"
  })

  const fetchStudents = () => {
    fetch("http://localhost:8000/students")
      .then(res => res.json())
      .then(data => setStudents(data))
  }

  useEffect(() => {
    fetchStudents()
  }, [])

  const handleSubmit = () => {
    fetch("http://localhost:8000/students", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        seat_number: parseInt(form.seat_number)
      })
    })
      .then(res => res.json())
      .then(() => {
        fetchStudents()
        setForm({
          seat_number: "",
          student_id: "",
          name: "",
          gender: "남",
          room_type: "정독"
        })
      })
  }

  return (
    <div style={{ padding: "20px" }}>
      <h1>자습실 관리 시스템</h1>

      <h2>학생 추가</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxWidth: "300px" }}>
        <input
          placeholder="좌석번호"
          value={form.seat_number}
          onChange={e => setForm({ ...form, seat_number: e.target.value })}
        />
        <input
          placeholder="학번"
          value={form.student_id}
          onChange={e => setForm({ ...form, student_id: e.target.value })}
        />
        <input
          placeholder="이름"
          value={form.name}
          onChange={e => setForm({ ...form, name: e.target.value })}
        />
        <select
          value={form.gender}
          onChange={e => setForm({ ...form, gender: e.target.value })}
        >
          <option value="남">남</option>
          <option value="여">여</option>
        </select>
        <select
          value={form.room_type}
          onChange={e => setForm({ ...form, room_type: e.target.value })}
        >
          <option value="정독">정독</option>
          <option value="일반">일반</option>
        </select>
        <button onClick={handleSubmit}>추가</button>
      </div>

      <h2>학생 목록 ({students.length}명)</h2>
      <table border="1" cellPadding="8">
        <thead>
          <tr>
            <th>좌석</th>
            <th>학번</th>
            <th>이름</th>
            <th>성별</th>
            <th>자습실</th>
          </tr>
        </thead>
        <tbody>
          {students.map(s => (
            <tr key={s.id}>
              <td>{s.seat_number}</td>
              <td>{s.student_id}</td>
              <td>{s.name}</td>
              <td>{s.gender}</td>
              <td>{s.room_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default App