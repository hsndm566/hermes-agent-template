async function api(path,opt={}){const r=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(opt.headers||{})},...opt});if(r.status===401){showLogin();throw Error('unauthorized')}const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||d.error||r.statusText);return d}
function showLogin(){$('loginCard').classList.remove('hidden');$('app').classList.add('hidden');$('logout').classList.add('hidden')}
function showApp(){$('loginCard').classList.add('hidden');$('app').classList.remove('hidden');$('logout').classList.remove('hidden')}
async function init(){applyLanguage();try{await api('/api/session');showApp();await loadBusinesses()}catch{showLogin()}}
$('login').onclick=async()=>{try{await api('/api/login',{method:'POST',body:JSON.stringify({username:$('user').value,password:$('pass').value})});$('loginMsg').textContent='';showApp();await loadBusinesses()}catch(e){$('loginMsg').textContent=lang==='ar'?'بيانات الدخول غير صحيحة.':'Incorrect login details.'}}
$('pass').addEventListener('keydown',e=>{if(e.key==='Enter')$('login').click()});
$('logout').onclick=async()=>{await api('/api/logout',{method:'POST'}).catch(()=>{});showLogin()};
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=async()=>{document.querySelectorAll('.tabs button,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active');if(b.dataset.tab==='bookings')await loadBookings()});
function onboardingServiceRow(s={}){
  let div=document.createElement('div');
  div.className='onboardingServiceRow';
  div.innerHTML=`<label><span>${lang==='ar'?'العربية':'Arabic'}</span><input class="o-ar" value="${escapeAttr(s.name_ar||'')}" placeholder="قص شعر"></label><label><span>English</span><input class="o-en" dir="ltr" value="${escapeAttr(s.name_en||'')}" placeholder="Haircut"></label><label><span>${t('duration')}</span><input class="o-duration" type="number" min="5" value="${s.duration_min||30}"></label><label><span>${t('price')}</span><input class="o-price" type="number" min="0" step="0.01" value="${s.price||0}"></label><label><span>${t('buffer')}</span><input class="o-buffer" type="number" min="0" value="${s.buffer_min||0}"></label><button class="deleteBtn onboardingDelete" type="button" title="${t('delete')}">×</button>`;
  div.querySelector('.onboardingDelete').onclick=()=>{if(document.querySelectorAll('#onboardingServices .onboardingServiceRow').length>1)div.remove()};
  return div;
}
function resetBusinessDialog(){
  $('businessForm').reset();
  $('createMsg').textContent='';
  $('botTone').value='friendly';
  $('onboardingServices').innerHTML='';
  $('onboardingServices').appendChild(onboardingServiceRow({name_ar:'قص شعر',name_en:'Haircut',duration_min:30,price:60,buffer_min:10}));
}
$('openAddBusiness').onclick=$('emptyAddBusiness').onclick=()=>{resetBusinessDialog();$('businessDialog').showModal()};
$('addOnboardingService').onclick=()=>$('onboardingServices').appendChild(onboardingServiceRow());

function defaultHours(){let a=[];for(let ram of [false,true])for(let d=0;d<7;d++)a.push({day_of_week:d,open_time:'10:00',close_time:'22:00',is_closed:d===5,is_ramadan:ram});return a}
$('createBusiness').onclick=async()=>{let btn=$('createBusiness');try{btn.disabled=true;btn.textContent=lang==='ar'?'جاري الإنشاء...':'Creating...';let sv=[...document.querySelectorAll('#onboardingServices .onboardingServiceRow')].map(r=>({name_ar:r.querySelector('.o-ar').value.trim(),name_en:r.querySelector('.o-en').value.trim(),duration_min:+r.querySelector('.o-duration').value,price:+r.querySelector('.o-price').value,buffer_min:+r.querySelector('.o-buffer').value})).filter(x=>x.name_ar&&x.name_en);if(!sv.length||sv.some(x=>!x.duration_min||x.duration_min<5||Number.isNaN(x.price)||x.price<0))throw Error(lang==='ar'?'تحقق من بيانات الخدمات.':'Check the service details.');let body={name_ar:$('nameAr').value.trim(),name_en:$('nameEn').value.trim(),phone:normalizePhone($('phone').value),maps_url:$('maps').value.trim(),latitude:null,longitude:null,vat_number:$('vat').value||null,cr_number:$('cr').value||null,bot_name_ar:$('botNameAr').value.trim()||null,bot_name_en:$('botNameEn').value.trim()||null,bot_tone:$('botTone').value,welcome_ar:$('welcomeAr').value.trim()||null,welcome_en:$('welcomeEn').value.trim()||null,services:sv,hours:defaultHours()};if(!body.name_ar||!body.name_en||!body.phone||!body.maps_url)throw Error(lang==='ar'?'أكمل الحقول المطلوبة.':'Complete all required fields.');let d=await api('/api/businesses',{method:'POST',body:JSON.stringify(body)});$('createMsg').innerHTML='<span class="ok">'+t('created')+'</span>';await loadBusinesses(d.id);if(d.qr)showQr(d.qr);setTimeout(()=>$('businessDialog').close(),600);toast(t('created'))}catch(e){$('createMsg').innerHTML='<span class="err">'+escapeHtml(e.message)+'</span>';toast(e.message,true)}finally{btn.disabled=false;btn.textContent=t('createConnect')}};
function normalizePhone(v){let p=v.replace(/\D/g,'');if(p.startsWith('05'))p='966'+p.slice(1);if(p.startsWith('5')&&p.length===9)p='966'+p;return p}
async function loadBusinesses(select){let rows=await api('/api/businesses');$('businessSelect').innerHTML=rows.map(x=>`<option value="${x.id}">${escapeHtml(lang==='ar'?x.name_ar:x.name_en)}</option>`).join('');if(select)$('businessSelect').value=select;if(rows.length){current=$('businessSelect').value;$('emptyState').classList.add('hidden');$('overviewContent').classList.remove('hidden');await loadDetail()}else{current=null;detail=null;$('emptyState').classList.remove('hidden');$('overviewContent').classList.add('hidden')}}
$('businessSelect').onchange=async()=>{current=$('businessSelect').value;await loadDetail()};
async function loadDetail(){if(!current)return;detail=await api('/api/businesses/'+current);renderServices();renderStaff();renderHours(detail.hours);renderSettings();renderProfile();await Promise.all([loadBookings(false),refreshConnection()]);renderOverview()}
