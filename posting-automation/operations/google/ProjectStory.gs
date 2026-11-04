/* build_publication.py가 실제 데이터가 포함된 실행용 .gs를 생성합니다. 템플릿 자체는 실행하지 마세요. */
const PROJECT_DECK = __DECK_JSON__;
const BLOGGER_POST = __POST_JSON__;
const PUBLICATION_READY = __READY_JSON__;
const BLOGGER_URL = __BLOG_URL_JSON__;

function createProjectSlides() {
  const properties = PropertiesService.getScriptProperties();
  const existing = properties.getProperty('PROJECT_DECK_ID');
  if (existing) {
    if (properties.getProperty('PROJECT_DECK_STATE') !== 'complete') throw new Error('이전 생성이 미완료입니다. 기록된 발표 자료를 먼저 확인하세요: ' + existing);
    Logger.log('기존 발표 자료: https://docs.google.com/presentation/d/' + existing + '/edit');
    return existing;
  }
  const presentation = SlidesApp.create(PROJECT_DECK.title);
  // 실패 시 다음 실행이 동일한 불완전 자료를 숨기지 않도록 ID를 먼저 기록합니다.
  const id = presentation.getId();
  properties.setProperty('PROJECT_DECK_ID', id);
  properties.setProperty('PROJECT_DECK_STATE', 'building');
  const width = presentation.getPageWidth(), height = presentation.getPageHeight();
  const initial = presentation.getSlides();
  PROJECT_DECK.slides.forEach(function(spec, index) {
    const slide = presentation.appendSlide(SlidesApp.PredefinedLayout.BLANK);
    slide.getBackground().setSolidFill('#FFFFFF');
    function text(value, x, y, w, h, size, color, bold) {
      const shape = slide.insertTextBox(value, width*x, height*y, width*w, height*h);
      shape.getText().getTextStyle().setFontFamily('Noto Sans KR').setFontSize(size).setForegroundColor(color).setBold(bold);
    }
    text(spec.tag, .055, .06, .9, .07, 13, '#087F8C', true);
    text(spec.title, .055, .18, .9, .20, 26, '#172B43', true);
    text(spec.body, .055, .40, .9, .43, 19, '#172B43', false);
    text((index+1) + ' / ' + PROJECT_DECK.slides.length + ' · ' + PROJECT_DECK.as_of, .055, .91, .9, .05, 10, '#52657C', false);
    slide.getNotesPage().getSpeakerNotesShape().getText().setText('근거:\n' + spec.evidence.join('\n'));
  });
  initial.forEach(function(slide) { slide.remove(); });
  presentation.saveAndClose();
  properties.setProperty('PROJECT_DECK_STATE', 'complete');
  Logger.log('발표 자료: https://docs.google.com/presentation/d/' + id + '/edit');
  return id;
}

function exportProjectPptx() {
  const properties = PropertiesService.getScriptProperties();
  const id = properties.getProperty('PROJECT_DECK_ID');
  if (!id || properties.getProperty('PROJECT_DECK_STATE') !== 'complete') throw new Error('먼저 createProjectSlides 완료 상태를 확인하세요.');
  const mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
  const response = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(id) + '/export?mimeType=' + encodeURIComponent(mime), {
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 200) throw new Error('PPTX 내보내기 실패: HTTP ' + response.getResponseCode());
  const upload = UrlFetchApp.fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=media&fields=id', {
    method: 'post', contentType: mime, payload: response.getBlob().getBytes(),
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true
  });
  if (upload.getResponseCode() !== 200) throw new Error('PPTX Drive 저장 결과 확인 필요: HTTP ' + upload.getResponseCode());
  const file = JSON.parse(upload.getContentText());
  const renamed = UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(file.id), {
    method: 'patch', contentType: 'application/json', payload: JSON.stringify({name:'project-story.pptx'}),
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() }, muteHttpExceptions: true
  });
  if (renamed.getResponseCode() !== 200) throw new Error('생성된 PPTX 이름 변경 실패. Drive에서 파일 ID 확인: ' + file.id);
  Logger.log('PPTX: https://drive.google.com/file/d/' + file.id + '/view');
  return file.id;
}

function createBloggerDraft() {
  if (!PUBLICATION_READY) throw new Error('서버 정리·사실 검토가 미완료입니다. 원본 근거 자료를 갱신하고 재생성하세요.');
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const properties = PropertiesService.getScriptProperties();
    const state = properties.getProperty('BLOGGER_DRAFT_STATE');
    if (state) throw new Error('이미 초안 요청 이력이 있습니다. Blogger에서 확인한 뒤 수동으로 상태를 검토하세요: ' + state);
    const headers = { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() };
    const lookup = UrlFetchApp.fetch('https://www.googleapis.com/blogger/v3/blogs/byurl?url=' + encodeURIComponent(BLOGGER_URL), { headers: headers, muteHttpExceptions: true });
    if (lookup.getResponseCode() !== 200) throw new Error('블로그 조회 실패: HTTP ' + lookup.getResponseCode());
    const blog = JSON.parse(lookup.getContentText());
    // 요청 중단/응답 유실 시 중복 초안 생성을 막기 위해 전송 전 기록합니다.
    properties.setProperty('BLOGGER_DRAFT_STATE', 'requesting');
    const response = UrlFetchApp.fetch('https://www.googleapis.com/blogger/v3/blogs/' + encodeURIComponent(blog.id) + '/posts?isDraft=true', {
      method: 'post', contentType: 'application/json', payload: JSON.stringify(BLOGGER_POST), headers: headers, muteHttpExceptions: true
    });
    if (response.getResponseCode() !== 200) {
      properties.setProperty('BLOGGER_DRAFT_STATE', 'check_required');
      throw new Error('초안 결과 확인 필요: HTTP ' + response.getResponseCode());
    }
    const post = JSON.parse(response.getContentText());
    properties.setProperty('BLOGGER_DRAFT_STATE', 'created');
    properties.setProperty('BLOGGER_DRAFT_ID', String(post.id));
    Logger.log('Blogger 초안 생성 완료. 게시 상태는 Blogger 관리 화면에서 확인하세요.');
    return post.id;
  } finally { lock.releaseLock(); }
}
