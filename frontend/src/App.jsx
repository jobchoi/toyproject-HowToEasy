import { useEffect, useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

function App() {
  // const [count, setCount] = useState(0)
  const[status, setStatus] = useState("확인 중...")

  useEffect(()=>{
    fetch("http://localhost:8000/health")
    .then(res => res.json())
    .then(data => setStatus(data.status))
    .catch(()=>setStatus("연결 실패"))
  }, [])
  return (
    <div>
      <h1>자습실 관리 시스템</h1>
      <p>API 상태: {status}</p>
    </div>
  )
}

export default App
