/* Pure mocks: no Google account or network. */
function verifyProjectStory(source) {
  function assert(value, message) { if (!value) throw new Error(message); }
  function context(script, failure) {
    const values = {}, counts = {slides:0, fetch:0};
    const store = {getProperty:k => values[k] || null, setProperty:(k,v) => {values[k]=v;}};
    const style = {};
    ['setFontFamily','setFontSize','setForegroundColor','setBold'].forEach(k => style[k]=()=>style);
    const shape = {getText:()=>({getTextStyle:()=>style,setText:()=>{}})};
    const slide = {getBackground:()=>({setSolidFill:()=>{}}),insertTextBox:()=>shape,getNotesPage:()=>({getSpeakerNotesShape:()=>shape})};
    const deck = {getId:()=> 'mock-deck',getPageWidth:()=>720,getPageHeight:()=>405,getSlides:()=>[{remove:()=>{}}],appendSlide:()=>{counts.slides++;return slide;},saveAndClose:()=>{}};
    const fetcher={fetch:(url)=>{
      counts.fetch++;
      const post = url.indexOf('/posts?') >= 0;
      if (post) assert(url.indexOf('isDraft=true')>=0,'draft only');
      return {getResponseCode:()=>post && failure ? 503 : 200,getContentText:()=>JSON.stringify({id:post?'post-id':'blog-id'})};
    }};
    const functions=new Function('SlidesApp','PropertiesService','Logger','UrlFetchApp','LockService','ScriptApp',script+';return {createProjectSlides,createBloggerDraft};')(
      {create:()=>deck,PredefinedLayout:{BLANK:'blank'}},{getScriptProperties:()=>store},{log:()=>{}},fetcher,{getScriptLock:()=>({waitLock:()=>{},releaseLock:()=>{}})},{getOAuthToken:()=> 'MOCK_TOKEN'});
    return {functions,values,counts};
  }
  let c=context(source,false);
  assert(c.functions.createProjectSlides()==='mock-deck','deck creation');
  const count=c.counts.slides;
  assert(count===13 && c.values.PROJECT_DECK_STATE==='complete','13 slides');
  c.functions.createProjectSlides();assert(c.counts.slides===count,'no duplicate deck');
  let blocked=false;try {c.functions.createBloggerDraft();} catch(e) {blocked=true;}
  assert(blocked && c.counts.fetch===0,'unfinished publication never contacts Blogger');
  c.values.PROJECT_DECK_STATE='building';blocked=false;
  try {c.functions.createProjectSlides();} catch(e) {blocked=true;}
  assert(blocked,'unfinished deck must be visible as incomplete');
  const ready=source.replace('const PUBLICATION_READY = false;','const PUBLICATION_READY = true;');
  c=context(ready,false);assert(c.functions.createBloggerDraft()==='post-id','draft response');
  const requests=c.counts.fetch;blocked=false;
  try {c.functions.createBloggerDraft();} catch(e) {blocked=true;}
  assert(blocked && c.counts.fetch===requests,'no duplicate draft');
  c=context(ready,true);blocked=false;
  try {c.functions.createBloggerDraft();} catch(e) {blocked=true;}
  assert(blocked && c.values.BLOGGER_DRAFT_STATE==='check_required','unknown result review');
  const failedRequests=c.counts.fetch;
  try {c.functions.createBloggerDraft();} catch(e) {}
  assert(c.counts.fetch===failedRequests,'no retry after uncertain result');
  return {mock_tests:'passed',slides:count,cloud_executed:false};
}
if (typeof module !== 'undefined') module.exports = verifyProjectStory;
