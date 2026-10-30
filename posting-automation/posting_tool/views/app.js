'use strict';
const $ = id => document.getElementById(id);
let files = [], current = null, token = '', dirty = false, busy = false, delivered = false;
let mode='plain', blocks=[], rawMode=false, templateKey=null, templateDirty=false, sourceDirty=false, articleRecords=[];
const status = (message, error = false) => { $('status').textContent = message; $('status').classList.toggle('error', error); };
function updateControls() {
  $('prepare').disabled = !(mode==='plain' ? $('plain-text').value.trim() : files.length) || busy;
  $('add-image').disabled=!current || rawMode || busy;
  $('apply-template').disabled=!current || dirty || busy;
  for(const id of ['save-template','clone-template','preview-template','new-template','refresh-library']) $(id).disabled=busy;
  $('example').disabled = busy;
  $('apply').disabled = !current || busy || !dirty;
  const enabled = current && !dirty && !busy && $('reviewed').checked;
  $('copy').disabled = !enabled;
  for (const [id, name] of [['download-md','article.md'],['download-html','article.html'],['download-zip','bundle.zip']]) {
    const link = $(id);
    link.classList.toggle('disabled', !enabled);
    link.setAttribute('aria-disabled', String(!enabled));
    if (enabled) link.href = `/api/previews/${current.id}/download/${name}`;
    else link.removeAttribute('href');
  }
  updateProgress();
}
function updateProgress() {
  const reviewed = current && !dirty && $('reviewed').checked;
  let phase = !current ? 1 : (dirty ? 2 : 3);
  const complete = [Boolean(current), Boolean(current && !dirty), Boolean(reviewed && delivered)];
  for (let i = 1; i <= 3; i++) {
    const active = i === phase && !complete[2];
    $('step'+i).classList.toggle('current', active);
    $('step'+i).classList.toggle('done', complete[i-1]);
    if(active) $('step'+i).setAttribute('aria-current','step');
    else $('step'+i).removeAttribute('aria-current');
    $('step-status-'+i).textContent = complete[i-1] ? (i===3 ? '전달 요청함' : '저장됨') : (active ? '진행 중' : '대기');
  }
  let label, instruction, action;
  if (!current) {
    label='1단계 · 자료 가져오기'; instruction=(mode==='plain' ? $('plain-text').value.trim() : files.length) ? '자료가 준비됐습니다. 제목과 템플릿을 확인하고 원고를 만드세요.' : '평문을 붙여넣거나 파일을 선택해 주세요.'; action=(mode==='plain' ? $('plain-text').value.trim() : files.length) ? '원고 만들기 →' : '자료 입력하기 →';
  } else if(dirty) {
    label='2단계 · 편집 내용 저장 필요'; instruction='수정한 내용이 아직 미리보기에 반영되지 않았습니다. 저장한 뒤 다시 검토하세요.'; action='편집 내용 저장 →';
  } else if(!reviewed) {
    label='3단계 · 내용과 출처 검토'; instruction='원고와 출처를 확인한 뒤 검토 체크를 해 주세요. 외부 플랫폼에는 게시되지 않았습니다.'; action='검토하러 가기 →';
  } else if(!delivered) {
    label='3단계 · 내보내기 준비됨'; instruction='본문 복사 또는 파일 받기를 선택하세요. 네이버 등 실제 게시는 별도입니다.'; action='내보내기로 이동 →';
  } else {
    label='파일 받기 요청 또는 본문 복사 완료'; instruction='다운로드한 파일이나 복사한 내용을 확인하세요. 외부 플랫폼의 게시 완료를 뜻하지 않습니다.'; action='내보내기 다시 보기 →';
  }
  $('phase-label').textContent=busy ? '원고 처리 중' : label;
  $('next-instruction').textContent=busy ? '현재 요청을 처리하고 있습니다. 완료되면 다음 단계를 안내합니다.' : instruction;
  $('next-action').textContent=action; $('next-action').disabled=busy;
}
$('next-action').onclick = () => {
  if(!current) {if(mode==='plain') {if($('plain-text').value.trim()) $('prepare').click(); else $('plain-text').focus();} else if(files.length) $('prepare').click(); else $('files').click();}
  else if(dirty) $('apply').click();
  else if(!$('reviewed').checked) {$('reviewed').scrollIntoView({behavior:'smooth',block:'center'}); $('reviewed').focus({preventScroll:true});}
  else $('download-zip').scrollIntoView({behavior:'smooth',block:'center'});
};
function fileList() {
  $('file-list').replaceChildren();
  files.forEach((file, index) => {
    const item = document.createElement('li'), label = document.createElement('span'), remove = document.createElement('button');
    label.textContent = `${file.name} · ${Math.ceil(new TextEncoder().encode(file.content).length / 1024)} KB`;
    remove.textContent = '×'; remove.setAttribute('aria-label', `${file.name} 제거`);
    remove.onclick = () => { files.splice(index,1); fileList(); };
    item.append(label, remove); $('file-list').append(item);
  });
  updateControls();
}
async function chooseFiles(selected) {
  try {
    if (!selected.length || selected.length > 20) throw new Error('자료 파일을 1~20개 선택해 주세요.');
    const next = []; let total = 0;
    for (const file of selected) {
      if (!/\.(md|txt)$/i.test(file.name)) throw new Error('현재는 Markdown(.md)과 텍스트(.txt) 파일만 지원합니다.');
      if (file.size > 256000) throw new Error(`${file.name}: 파일 크기는 256KB 이하여야 합니다.`);
      total += file.size;
      if (total > 1000000) throw new Error('자료 전체 크기는 1MB 이하여야 합니다.');
      let content;
      try { content = new TextDecoder('utf-8', {fatal:true}).decode(await file.arrayBuffer()); }
      catch { throw new Error(`${file.name}: UTF-8로 저장한 파일을 선택해 주세요.`); }
      next.push({name:file.name, content});
    }
    files = next; setMode('file'); sourceDirty=true; fileList(); status(`${files.length}개 자료를 선택했습니다. 제목을 확인하고 원고를 만들어 주세요.`);
  } catch (error) { status(error.message, true); }
}
async function api(url, data) {
  const response = await fetch(url, data ? {method:'POST', headers:{'Content-Type':'application/json','X-Workspace-Token':token}, body:JSON.stringify(data)} : {});
  if (!response.ok) {
    let message = '처리하지 못했습니다. 연결 상태를 확인하고 다시 시도하세요.';
    try { const detail = await response.json(); if(typeof detail.detail === 'string') message = detail.detail; } catch {}
    throw new Error(message);
  }
  return response.json();
}
function show(result) {
  current = result; dirty = false; delivered = false; sourceDirty=false;
  blocks=result.blocks; rawMode=false; $('markdown').hidden=true; $('document-editor').hidden=false; $('toggle-editor').textContent='Markdown 보기'; renderBlocks();
  $('title').value = result.title; $('markdown').value = result.markdown;
  $('preview').srcdoc = result.html;
  $('warnings').replaceChildren();
  result.warnings.forEach(warning => { const item = document.createElement('li'); item.textContent = warning; $('warnings').append(item); });
  $('reviewed').checked = false;
  $('empty-state').hidden = true; $('editing').hidden = false;
  $('save-state').textContent = `자료 ${result.source_count}개 · 이 PC에 저장됨 · 게시 전 검토 필요`;
  sessionStorage.setItem('posting-preview',result.id);
  updateControls(); loadLibrary();
}
async function run(operation) {
  if(busy) return;
  busy = true; updateControls();
  $('processing').hidden=false; $('processing').classList.add('running'); $('processing').classList.remove('failed');
  $('processing').setAttribute('aria-busy','true'); $('processing-label').textContent='요청을 처리하고 있습니다'; $('processing-stages').replaceChildren();
  const started=Date.now();
  const clock=setInterval(()=>{$('processing-time').textContent=`경과 ${Math.floor((Date.now()-started)/1000)}초`;},1000);
  const disabled=[...document.querySelectorAll('input,textarea,select,button')].map(el=>[el,el.disabled]);
  disabled.forEach(([el])=>{el.disabled=true;});
  try { await operation(); $('processing-label').textContent='처리를 마쳤습니다. 다음 단계를 확인하세요.'; }
  catch(error) {$('processing-label').textContent='처리를 완료하지 못했습니다';$('processing').classList.add('failed');status(error.message, true);}
  finally { clearInterval(clock);$('processing-time').textContent=`경과 ${Math.floor((Date.now()-started)/1000)}초`;
    disabled.forEach(([el,value])=>{if(el.isConnected)el.disabled=value;});
    $('processing').classList.remove('running');$('processing').setAttribute('aria-busy','false');busy = false; updateControls(); }
}
async function waitJob(id) {
  sessionStorage.setItem('posting-job',id);
  while(true) {
    const job=await api('/api/jobs/'+id);
    $('processing-stages').replaceChildren();
    for(const item of job.stages) {const li=document.createElement('li');li.className=item.state;li.textContent=({pending:'○ ',running:'◉ ',done:'✓ ',failed:'! '}[item.state]||'')+item.name;$('processing-stages').append(li);}
    const running=job.stages.find(s=>s.state==='running');$('processing-label').textContent=running?running.name+' 중':job.state==='queued'?'순서를 기다리고 있습니다':'결과 확인 중';
    if(job.state==='succeeded') {sessionStorage.removeItem('posting-job');return api('/api/previews/'+job.result_id);}
    if(['failed','interrupted'].includes(job.state)) {sessionStorage.removeItem('posting-job');throw new Error(job.error);}
    await new Promise(resolve=>setTimeout(resolve,250));
  }
}
async function prepareJob(payload) {const job=await api('/api/jobs',payload);return waitJob(job.id);}

$('dropzone').addEventListener('keydown', event => { if(event.key === 'Enter' || event.key === ' ') {event.preventDefault(); $('files').click();} });
$('files').addEventListener('change', event => chooseFiles([...event.target.files]));
for(const name of ['dragover','dragleave','drop']) $('dropzone').addEventListener(name, event => {
  event.preventDefault(); $('dropzone').classList.toggle('dragover',name==='dragover');
  if(name==='drop') chooseFiles([...event.dataTransfer.files]);
});
$('example').onclick = () => run(async () => {
  if (dirty && !confirm('저장하지 않은 편집 내용이 있습니다. 예제로 새 원고를 만들까요?')) return;
  status('예제 자료를 가져오는 중입니다…');
  const example = await api('/api/example'); files = example.files; setMode('file'); fileList();
  show(await prepareJob({files,template_id:$('template').value})); status('예제 원고를 만들었습니다. 내용을 수정하고 미리보기를 확인해 보세요.');
});
$('prepare').onclick = () => run(async () => {
  if (dirty && !confirm('저장하지 않은 편집 내용이 있습니다. 자료로 새 원고를 만들까요?')) return;
  status('자료를 정리하고 원고를 만드는 중입니다…');
  show(await prepareJob({...(mode==='plain' ? {text:$('plain-text').value} : {files}), title:$('title').value,template_id:$('template').value}));
  status('원고가 준비됐습니다. 내용을 다듬고 출처를 확인해 주세요.');
  $('workspace').scrollIntoView({behavior:'smooth',block:'start'});
});
function markDirty() {
  if (!current) return;
  dirty = true; delivered = false; $('reviewed').checked = false;
  $('save-state').textContent = '저장하지 않은 변경이 있습니다. 미리보기와 내보내기를 갱신해 주세요.';
  updateControls();
}
$('markdown').addEventListener('input',markDirty); $('title').addEventListener('input',markDirty);
$('apply').onclick = () => run(async () => {
  status('편집 내용을 새 버전으로 저장하는 중입니다…');
  show(await api(`/api/previews/${current.id}`,{title:$('title').value, ...(rawMode ? {markdown:$('markdown').value} : {blocks})}));
  status('편집 내용과 미리보기를 저장했습니다. 내용을 다시 확인해 주세요.');
});
$('reviewed').onchange = () => {delivered=false; updateControls();};
for(const id of ['download-md','download-html','download-zip']) $(id).addEventListener('click', () => { if(current && !dirty && $('reviewed').checked) {delivered=true; updateControls();} });
$('copy').onclick = async () => {
  try { await navigator.clipboard.writeText(current.blocks.map(b=>b.type==='image'?`[사진: ${b.text}]\n${b.caption||''}\n${b.source||''}`:b.type==='list'?b.text.split('\n').map(x=>'• '+x).join('\n'):b.type==='divider'?'────────':b.text).join('\n\n')); delivered=true; updateControls(); status('일반 본문을 복사했습니다. 붙여넣은 뒤 플랫폼 서식을 확인해 주세요.'); }
  catch { status('클립보드 접근이 제한됐습니다. 원고 영역을 직접 선택하거나 Markdown 파일을 받아 주세요.',true); }
};
window.addEventListener('beforeunload', event => { if(dirty || sourceDirty || templateDirty) {event.preventDefault(); event.returnValue='';} });
(async () => {
  try {
    token = (await api('/api/config')).token;
    const pendingJob=sessionStorage.getItem('posting-job');
    if(pendingJob) await run(async()=>{show(await waitJob(pendingJob));status('이전 원고 처리 결과를 불러왔습니다.');});
    const key = sessionStorage.getItem('posting-preview');
    if(key) {
      try { show(await api(`/api/previews/${key}`)); status('마지막 원고를 불러왔습니다. 내용을 확인한 뒤 내보내세요.'); }
      catch {sessionStorage.removeItem('posting-preview');}
    }
    updateControls();
    await Promise.all([loadTemplates(),loadLibrary(),loadSamples()]);
  } catch {status('작업 공간에 연결하지 못했습니다. 서버 실행 상태를 확인하고 새로고침해 주세요.',true);}
})();


function setMode(value) {
  mode=value;
  $('paste-input').hidden=value!=='plain'; $('file-input').hidden=value!=='file';
  $('plain-mode').setAttribute('aria-pressed',String(value==='plain')); $('file-mode').setAttribute('aria-pressed',String(value==='file'));
  updateControls();
}
$('plain-mode').onclick=()=>setMode('plain'); $('file-mode').onclick=()=>setMode('file');
$('plain-text').addEventListener('input',()=>{sourceDirty=true; updateControls();});
function renderBlocks() {
  $('blocks').replaceChildren();
  const names={title:'큰 제목',heading:'소제목',subheading:'작은 소제목',paragraph:'본문',list:'목록',divider:'구분선',image:'사진'};
  blocks.forEach((block,index)=>{
    const box=document.createElement('div');box.className='document-block '+block.type;
    const tools=document.createElement('div');tools.className='block-tools';
    const select=document.createElement('select');select.setAttribute('aria-label',`${index+1}번 문단 유형`);
    for(const [type,label] of Object.entries(names)) {const option=document.createElement('option');option.value=type;option.textContent=label;select.append(option);}
    select.value=block.type;
    if(block.type==='image') select.disabled=true;
    else select.querySelector('option[value="image"]').remove();
    select.onchange=()=>{block.type=select.value;if(['title','heading','subheading'].includes(block.type)) block.text=block.text.replace(/\n/g,' ');markDirty();renderBlocks();};
    tools.append(select);
    for(const [label,action] of [['↑',()=>{if(index>0) [blocks[index-1],blocks[index]]=[blocks[index],blocks[index-1]];}],['↓',()=>{if(index<blocks.length-1) [blocks[index+1],blocks[index]]=[blocks[index],blocks[index+1]];}],['삭제',()=>{blocks.splice(index,1);}]]) {
      const button=document.createElement('button');button.type='button';button.textContent=label;button.setAttribute('aria-label',`${index+1}번 문단 ${label}`);
      button.onclick=()=>{action();markDirty();renderBlocks();};tools.append(button);
    }
    box.append(tools);
    if(block.type==='image') {
      const image=document.createElement('img');image.src=current.images?.[block.src]||'';image.alt=block.text;image.style.maxWidth='100%';box.append(image);
      for(const [key,label] of [['text','사진 대체 설명'],['caption','사진 캡션'],['source','사진 출처 URL']]) {
        const wrapper=document.createElement('label');wrapper.textContent=label;
        const field=document.createElement('input');field.value=block[key]||'';field.maxLength=1000;field.setAttribute('aria-label',`${index+1}번 ${label}`);
        field.oninput=()=>{block[key]=field.value;markDirty();};wrapper.append(field);box.append(wrapper);
      }
    }
    else if(block.type==='divider') {const hr=document.createElement('hr');box.append(hr);}
    else {const field=document.createElement('textarea');field.value=block.text;field.rows=['title','heading','subheading'].includes(block.type)?1:Math.max(3,Math.min(10,block.text.split('\n').length+1));field.setAttribute('aria-label',`${index+1}번 ${names[block.type]}`);field.placeholder='내용을 입력하세요';field.oninput=()=>{block.text=field.value;markDirty();};box.append(field);}
    $('blocks').append(box);
  });
}
$('add-image').onclick=()=>$('image-file').click();
$('image-file').onchange=()=>run(async()=>{
  const file=$('image-file').files[0];if(!file)return;
  try {
    if(file.size>700000)throw new Error('사진은 700KB 이하로 줄여 주세요.');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('사진을 읽지 못했습니다.'));reader.readAsDataURL(file);});
    const result=await api('/api/media',{content:data.split(',')[1]});
    current.images={...(current.images||{}),[result.src]:data};
    blocks.push({type:'image',text:file.name.replace(/[\[\]\r\n]/g,''),src:result.src,caption:'',source:''});
    renderBlocks();markDirty();status('사진을 추가했습니다. 캡션과 출처를 입력하고 편집 내용을 저장하세요.');
  } finally {$('image-file').value='';}
});
$('add-block').onclick=()=>{blocks.push({type:'paragraph',text:''});renderBlocks();markDirty();$('blocks').lastElementChild.querySelector('textarea').focus();};
function blocksMarkdown() {
  const prefix={title:'# ',heading:'## ',subheading:'### '};
  return blocks.map(b=>b.type==='image'?`![${b.text}](${b.src})\n사진 설명: ${b.caption||''}\n사진 출처: ${b.source||''}`:b.type==='divider'?'---':b.type==='list'?b.text.split('\n').filter(x=>x.trim()).map(x=>'- '+x.replace(/^[-•· ]+/, '')).join('\n'):(prefix[b.type]||'')+b.text).join('\n\n');
}
$('toggle-editor').onclick=()=>run(async()=>{
  if(rawMode) {blocks=(await api('/api/document-blocks',{markdown:$('markdown').value})).blocks;renderBlocks();}
  else $('markdown').value=blocksMarkdown();
  rawMode=!rawMode;$('markdown').hidden=!rawMode;$('document-editor').hidden=rawMode;$('toggle-editor').textContent=rawMode?'문서 편집으로':'Markdown 보기';
});
async function loadLibrary() {
  try {articleRecords=(await api('/api/previews')).articles;renderLibrary();}
  catch {$('article-list').textContent='원고 목록을 불러오지 못했습니다.';}
}
function renderLibrary() {
  $('article-list').replaceChildren();
  const filtered=articleRecords.filter(r=>r.title.toLowerCase().includes($('article-search').value.toLowerCase()));
  if(!filtered.length) {$('article-list').textContent='저장된 원고가 없습니다.';return;}
  for(const record of filtered) {
    const row=document.createElement('div');row.className='article-row';
    const label=document.createElement('div'), title=document.createElement('strong'),meta=document.createElement('small');
    title.textContent=record.title;meta.textContent=new Date(record.saved_at).toLocaleString('ko-KR');label.append(title,meta);
    const open=document.createElement('button');open.className='secondary';open.textContent='이어쓰기';open.onclick=()=>openArticle(record.id);
    const history=document.createElement('button');history.className='secondary';history.textContent='이전 버전';
    const details=document.createElement('div');details.className='version-list';details.hidden=true;
    history.onclick=()=>run(async()=>{
      const all=(await api('/api/previews?history=true')).articles.filter(r=>r.article_id===record.article_id);
      details.replaceChildren();for(const version of all) {const button=document.createElement('button');button.className='secondary';button.textContent=new Date(version.saved_at).toLocaleString('ko-KR')+(version.id===record.id?' · 최신':'');button.onclick=()=>openArticle(version.id);details.append(button);} details.hidden=!details.hidden;
    });
    row.append(label,open,history);const wrapper=document.createElement('div');wrapper.append(row,details);$('article-list').append(wrapper);
  }
}
async function openArticle(id) {
  if(dirty && !confirm('저장하지 않은 내용이 있습니다. 다른 원고를 열까요?')) return;
  await run(async()=>{show(await api('/api/previews/'+id));status('저장한 원고를 열었습니다. 수정 후 저장하면 새 버전이 됩니다.');$('workspace').scrollIntoView({behavior:'smooth'});});
}
$('refresh-library').onclick=loadLibrary; $('article-search').oninput=renderLibrary;
let templateRecords=[];
function templateForm() {return {name:$('template-name').value,intro:$('template-intro').value,sections:$('template-sections').value.split('\n').map(x=>x.trim()).filter(Boolean),outro:$('template-outro').value,style:$('template-style').value,appearance:designValues()};}
function showTemplate(value) {clearTimeout(studioTimer);studioRequest++;showDesign(value.appearance||{});templateKey=value.id||null;$('template-style').value=value.style||'plain';$('template-name').value=value.name||'';$('template-intro').value=value.intro||'';$('template-sections').value=(value.sections||[]).join('\n');$('template-outro').value=value.outro||'';templateDirty=false;$('template-status').textContent=value.builtin?'기본 템플릿은 직접 덮어쓰지 않고 새 템플릿으로 저장합니다.':value.version?`저장 버전 ${value.version} · 수정해 저장하면 새 버전이 됩니다.`:'새 템플릿을 작성하세요.';}
async function loadTemplates(selected) {
  const response=await api('/api/templates');templateRecords=response.templates;
  const previous=selected||$('template').value;
  for(const id of ['template','manage-template']) {const select=$(id);select.replaceChildren();for(const value of templateRecords) {const option=document.createElement('option');option.value=value.id;option.textContent=`${value.name} · v${value.version}`;select.append(option);} if(templateRecords.some(t=>t.id===previous)) select.value=previous;}
  showTemplate(templateRecords.find(t=>t.id===$('manage-template').value)||templateRecords[0]);
  scheduleChoicePreview();
}
$('manage-template').onchange=()=>{
  if(templateDirty && !confirm('저장하지 않은 템플릿 내용을 바꿀까요?')) {if(templateKey) $('manage-template').value=templateKey;return;}
  showTemplate(templateRecords.find(t=>t.id===$('manage-template').value));scheduleStudioPreview();
};
for(const id of ['template-name','template-intro','template-sections','template-outro','template-style']) $(id).addEventListener('input',()=>{templateDirty=true;scheduleStudioPreview();});
$('new-template').onclick=()=>{if(templateDirty&&!confirm('작성 중인 템플릿을 비우고 새로 만들까요?'))return;showTemplate({});$('template-name').focus();};
function saveTemplate(clone) {clearTimeout(studioTimer);studioRequest++;return run(async()=>{const data={...templateForm(),clone};const saved=await api(templateKey?'/api/templates/'+templateKey:'/api/templates',data);templateDirty=false;await loadTemplates(saved.id);$('template-status').textContent=`${clone?'복제':'저장'}했습니다. 생성된 원고는 바뀌지 않으며 다음 원고에 선택해 적용할 수 있습니다.`;status('템플릿을 저장했습니다.');});}
$('save-template').onclick=()=>saveTemplate(false);$('clone-template').onclick=()=>saveTemplate(true);
$('preview-template').onclick=()=>run(async()=>{const value=await api('/api/template-preview',{template:templateForm(),text:$('plain-text').value.trim()||'자료의 본문이 여기에 들어갑니다.'});$('template-preview').srcdoc=value.html;$('template-status').textContent='저장하지 않은 내용의 미리보기입니다.';});
$('apply-template').onclick=()=>run(async()=>{
  if(!current || dirty) throw new Error('먼저 원고 편집 내용을 저장하세요.');
  show(await api(`/api/previews/${current.id}/template`,{template_id:$('template').value}));status('템플릿을 적용한 별도 사본을 만들었습니다. 원본은 보존됩니다.');
});


async function loadSamples() {
  try {
    const {samples}=await api('/api/template-samples');$('sample-gallery').replaceChildren();
    for(const sample of samples) {
      const card=document.createElement('article');card.className='sample-card '+sample.style;
      const title=document.createElement('h3');title.textContent=sample.name;
      const description=document.createElement('p');description.textContent=sample.description;
      const frame=document.createElement('iframe');frame.title=sample.name+' 미리보기';frame.setAttribute('sandbox','');frame.srcdoc=sample.html;
      const buttons=document.createElement('div');buttons.className='sample-actions';
      const large=document.createElement('button');large.className='secondary';large.textContent='크게 보기';large.onclick=()=>{$('sample-dialog-title').textContent=sample.name;$('sample-large').srcdoc=sample.html;$('sample-dialog').showModal();};
      const select=document.createElement('button');select.className='secondary';select.textContent='템플릿 선택';select.onclick=()=>{
        if(templateDirty && !confirm('저장하지 않은 템플릿 내용을 바꿀까요?'))return;
        $('template').value=sample.id;$('manage-template').value=sample.id;showTemplate(sample);scheduleChoicePreview();scheduleStudioPreview();status(sample.name+'을 선택했습니다. 다음 원고에 적용하거나 사본 만들기를 사용하세요.');
      };
      const open=document.createElement('button');open.className='primary';open.textContent='샘플 원고 열기';open.onclick=()=>run(async()=>{
        if(dirty && !confirm('저장하지 않은 원고가 있습니다. 샘플을 열까요?'))return;
        show(await api('/api/template-samples/'+sample.id,{}));status('가상 샘플 원고를 저장했습니다. 내용과 디자인을 편집해 볼 수 있습니다.');$('workspace').scrollIntoView({behavior:'smooth'});
      });
      buttons.append(large,select,open);card.append(frame,title,description,buttons);$('sample-gallery').append(card);
    }
  } catch {$('sample-gallery').textContent='샘플을 불러오지 못했습니다. 화면을 새로고침해 주세요.';}
}
$('close-sample').onclick=()=>$('sample-dialog').close();


let choiceTimer,studioTimer,choiceRequest=0,studioRequest=0;
function scheduleChoicePreview() {
  clearTimeout(choiceTimer);const request=++choiceRequest;choiceTimer=setTimeout(async()=>{$('choice-status').textContent='선택한 템플릿을 불러오는 중…';
    try {const value=await api('/api/template-choice-preview',{template_id:$('template').value,...(current?{markdown:rawMode?$('markdown').value:blocksMarkdown()}:{text:mode==='plain'?$('plain-text').value:files.map(f=>f.content).join('\n\n')})});
      if(request!==choiceRequest)return;$('choice-preview').srcdoc=value.html;$('choice-status').textContent=value.name+' · 저장하지 않은 미리보기';
    } catch(error) {if(request===choiceRequest)$('choice-status').textContent=error.message;}
  },200);
}
function scheduleStudioPreview() {
  clearTimeout(studioTimer);const request=++studioRequest;studioTimer=setTimeout(async()=>{
    if(!$('template-name').value.trim())return;$('template-status').textContent='디자인 미리보기 갱신 중…';
    try {const value=await api('/api/template-preview',{template:templateForm(),text:$('plain-text').value.trim()||'자료의 본문이 여기에 들어갑니다.'});
      if(request!==studioRequest)return;$('template-preview').srcdoc=value.html;$('template-status').textContent='선택/수정 내용이 바로 반영된 미리보기입니다. 저장은 별도입니다.';
    } catch(error) {if(request===studioRequest)$('template-status').textContent=error.message;}
  },350);
}
$('template').addEventListener('change',scheduleChoicePreview);
$('plain-text').addEventListener('input',scheduleChoicePreview);


const designFields={background:'design-background',text:'design-text',accent:'design-accent',font:'design-font',body_size:'design-size',line_height:'design-line',content_width:'design-width',paragraph_gap:'design-gap',heading:'design-heading'};
function designValues() {
  if(!$('design-enabled').checked)return {};
  return Object.fromEntries(Object.entries(designFields).map(([key,id])=>[key,['body_size','line_height','content_width','paragraph_gap'].includes(key)?Number($(id).value):$(id).value]));
}
function showDesign(value) {
  $('design-enabled').checked=Object.keys(value).length>0;
  const defaults={background:'#ffffff',text:'#243143',accent:'#276351',font:'sans',body_size:17,line_height:1.8,content_width:800,paragraph_gap:18,heading:'plain'};
  for(const [key,id] of Object.entries(designFields))$(id).value=value[key]??defaults[key];
}
for(const id of ['design-enabled',...Object.values(designFields)]) $(id).addEventListener('input',()=>{templateDirty=true;scheduleStudioPreview();});


// Navigation describes document locations; editing progress is a separate state.
const workspaceLinks = [...document.querySelectorAll('.workspace-nav a[href^="#"]')];
const workspaceSections = workspaceLinks.map(link => document.querySelector(link.getAttribute('href')));
function navigationOffset() {
  return matchMedia('(max-width:760px)').matches ? document.querySelector('.sidebar').getBoundingClientRect().height + 16 : 24;
}
function updateNavigation() {
  const offset = navigationOffset();
  document.documentElement.style.setProperty('--navigation-offset', `${offset}px`);
  let currentIndex = 0;
  workspaceSections.forEach((section, index) => {
    if(section.getBoundingClientRect().top <= offset + 48) currentIndex = index;
  });
  workspaceLinks.forEach((link, index) => {
    link.classList.toggle('active', index === currentIndex);
    if(index === currentIndex) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  $('current-location').textContent = workspaceLinks[currentIndex].dataset.label;
}
let navigationFrame = null;
function scheduleNavigation() {
  if(navigationFrame !== null) return;
  navigationFrame = requestAnimationFrame(() => {navigationFrame = null; updateNavigation();});
}
workspaceLinks.forEach((link, index) => {
  link.addEventListener('click', () => {
    // Native anchors preserve deep links and Back/Forward, including keyboard activation.
    workspaceSections[index].focus({preventScroll:true});
    scheduleNavigation();
  });
});
addEventListener('scroll', scheduleNavigation, {passive:true});
addEventListener('resize', scheduleNavigation);
addEventListener('hashchange', scheduleNavigation);
new ResizeObserver(scheduleNavigation).observe(document.querySelector('main'));
updateNavigation();
