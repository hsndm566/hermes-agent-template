# SOURCE EXPORT CHUNK 4/4



---

## whatsapp-bot/frontend/i18n.js

```javascript
const $=id=>document.getElementById(id);
let current=null,detail=null,appointmentsCache=[],lang=localStorage.getItem('bookingLang')||'ar',hoursMode='normal';
const i18n={
 ar:{brandSub:'حجوزات واتساب للمنشآت',logout:'تسجيل الخروج',welcome:'أهلاً بك',loginHelp:'ادخل لوحة التحكم لإدارة الحجوزات وربط واتساب.',username:'اسم المستخدم',password:'كلمة المرور',login:'دخول',currentBusiness:'المنشأة الحالية',addBusiness:'+ إضافة منشأة',overview:'الرئيسية',bookings:'الحجوزات',services:'الخدمات',hours:'ساعات العمل',settings:'الإعدادات',firstBusiness:'أضف أول منشأة',firstBusinessHelp:'أدخل اسم المنشأة وخدمة واحدة على الأقل. بعدها سيظهر QR لربط واتساب.',startSetup:'ابدأ الإعداد',status:'الحالة',checking:'جاري التحقق',todayBookings:'حجوزات اليوم',upcomingBookings:'الحجوزات القادمة',servicesCount:'الخدمات',setup:'الإعداد',goLive:'تشغيل المنشأة',businessAdded:'تمت إضافة المنشأة',businessAddedHelp:'الاسم والخدمات الأساسية محفوظة.',connectWhatsapp:'اربط واتساب',connectWhatsappHelp:'امسح رمز QR من الأجهزة المرتبطة في واتساب.',readyForCustomers:'ابدأ استقبال العملاء',readyHelp:'بعد الاتصال يستطيع العملاء مراسلة الرقم مباشرة.',scanQr:'امسح QR من واتساب',scanHelp:'واتساب ← الإعدادات ← الأجهزة المرتبطة ← ربط جهاز',newQr:'تحديث QR',next:'التالي',nextBookings:'أقرب الحجوزات',refresh:'تحديث',manage:'إدارة',customer:'العميل',phone:'الهاتف',service:'الخدمة',staff:'الموظف',time:'الوقت',bookingStatus:'الحالة',catalog:'القائمة',addService:'+ خدمة',serviceHelp:'حدد الاسم والمدة والسعر. وقت التجهيز يمنع حجز موعد آخر مباشرة بعد الخدمة.',saveChanges:'حفظ التغييرات',schedule:'الجدول',normalHours:'الأيام العادية',ramadanHours:'رمضان',saveHours:'حفظ ساعات العمل',automation:'الأتمتة',bookingRules:'قواعد الحجز',ramadanMode:'تفعيل جدول رمضان',ramadanModeHelp:'استخدم ساعات رمضان بدلاً من الجدول العادي.',prayerBlock:'حجب وقت الصلاة',prayerBlockHelp:'يمنع المواعيد حول أوقات الصلاة.',prayerBuffer:'مدة الحجب حول الصلاة بالدقائق',slotInterval:'الفاصل بين الأوقات المتاحة بالدقائق',policies:'السياسات',cancellation:'سياسة الإلغاء',saveSettings:'حفظ الإعدادات',quickSetup:'إعداد سريع',addBusinessTitle:'أضف منشأة جديدة',addBusinessHelp:'نحتاج المعلومات الأساسية فقط. يمكنك تعديل كل شيء لاحقاً.',businessNameAr:'اسم المنشأة بالعربي',businessNameEn:'Business name in English',ownerPhone:'رقم واتساب',mapsLink:'رابط Google Maps',invoiceDetails:'بيانات المنشأة والفوترة الاختيارية',vat:'الرقم الضريبي',cr:'رقم السجل التجاري',firstServices:'الخدمات الأولى',serviceInputHelp:'أضف خدمة واحدة على الأقل. يمكنك إضافة المزيد لاحقاً.',createConnect:'إنشاء وربط واتساب',cancel:'إلغاء',connected:'واتساب متصل',notConnected:'واتساب غير متصل',noBookings:'لا توجد حجوزات قادمة.',saved:'تم الحفظ',created:'تم إنشاء المنشأة. اربط واتساب لإكمال التشغيل.',delete:'حذف',duration:'المدة',price:'السعر',buffer:'تجهيز',closed:'مغلق',sar:'ر.س',minutes:'دقيقة',normal:'عادي',ramadan:'رمضان',staffTab:'الموظفون',team:'الفريق',addStaff:'+ موظف',staffHelp:'أضف الأشخاص الذين يمكن الحجز لديهم. يوزع النظام المواعيد على أول موظف متاح.',saveStaff:'حفظ الموظفين',active:'نشط',businessProfile:'بيانات المنشأة',businessProfileHelp:'البيانات التي تظهر في الحجز والتأكيد',saveProfile:'حفظ بيانات المنشأة',botPersonality:'شخصية البوت',botPersonalityHelp:'خصص الاسم والأسلوب ورسالة الترحيب. العميل يختار العربية أو الإنجليزية في أول رسالة.',botSetupHelp:'اختر كيف يتحدث البوت مع عملاء هذه المنشأة.',botNameAr:'اسم البوت بالعربي',botNameEn:'اسم البوت بالإنجليزية',botTone:'الأسلوب',toneFriendly:'ودود',toneProfessional:'احترافي',toneLuxury:'راقي',toneConcise:'مختصر',welcomeAr:'رسالة ترحيب عربية اختيارية',welcomeEn:'رسالة ترحيب إنجليزية اختيارية',languageChoiceHelp:'أول رسالة من أي عميل جديد ستكون: اختر اللغة / Choose your language.'},
 en:{brandSub:'WhatsApp booking for service businesses',logout:'Log out',welcome:'Welcome',loginHelp:'Sign in to manage bookings and connect WhatsApp.',username:'Username',password:'Password',login:'Sign in',currentBusiness:'Current business',addBusiness:'+ Add business',overview:'Overview',bookings:'Bookings',services:'Services',hours:'Working hours',settings:'Settings',firstBusiness:'Add your first business',firstBusinessHelp:'Enter the business name and at least one service. Then connect WhatsApp with a QR code.',startSetup:'Start setup',status:'Status',checking:'Checking',todayBookings:'Today',upcomingBookings:'Upcoming',servicesCount:'Services',setup:'Setup',goLive:'Go live',businessAdded:'Business added',businessAddedHelp:'Basic business details and services are saved.',connectWhatsapp:'Connect WhatsApp',connectWhatsappHelp:'Scan the QR from WhatsApp Linked Devices.',readyForCustomers:'Start receiving customers',readyHelp:'Once connected, customers can message the number directly.',scanQr:'Scan with WhatsApp',scanHelp:'WhatsApp → Settings → Linked Devices → Link a Device',newQr:'Refresh QR',next:'Next',nextBookings:'Upcoming bookings',refresh:'Refresh',manage:'Manage',customer:'Customer',phone:'Phone',service:'Service',staff:'Staff',time:'Time',bookingStatus:'Status',catalog:'Catalog',addService:'+ Service',serviceHelp:'Set the name, duration and price. Buffer blocks the period immediately after a service.',saveChanges:'Save changes',schedule:'Schedule',normalHours:'Regular days',ramadanHours:'Ramadan',saveHours:'Save working hours',automation:'Automation',bookingRules:'Booking rules',ramadanMode:'Use Ramadan schedule',ramadanModeHelp:'Use Ramadan hours instead of the regular schedule.',prayerBlock:'Block prayer times',prayerBlockHelp:'Prevents appointments around prayer times.',prayerBuffer:'Prayer buffer in minutes',slotInterval:'Available-slot interval in minutes',policies:'Policies',cancellation:'Cancellation policy',saveSettings:'Save settings',quickSetup:'Quick setup',addBusinessTitle:'Add a new business',addBusinessHelp:'Only the basics are required. Everything can be edited later.',businessNameAr:'Arabic business name',businessNameEn:'English business name',ownerPhone:'WhatsApp number',mapsLink:'Google Maps link',invoiceDetails:'Optional business and invoice details',vat:'VAT number',cr:'CR number',firstServices:'First services',serviceInputHelp:'Add at least one service. You can add more later.',createConnect:'Create and connect WhatsApp',cancel:'Cancel',connected:'WhatsApp connected',notConnected:'WhatsApp not connected',noBookings:'No upcoming bookings.',saved:'Saved',created:'Business created. Connect WhatsApp to finish setup.',delete:'Delete',duration:'Duration',price:'Price',buffer:'Buffer',closed:'Closed',sar:'SAR',minutes:'min',normal:'Regular',ramadan:'Ramadan',staffTab:'Staff',team:'Team',addStaff:'+ Staff',staffHelp:'Add people who can receive bookings. The system assigns the first available team member.',saveStaff:'Save staff',active:'Active',businessProfile:'Business profile',businessProfileHelp:'Details used in bookings and confirmations',saveProfile:'Save business profile',botPersonality:'Bot personality',botPersonalityHelp:'Customize the name, tone and greeting. New customers choose Arabic or English on their first message.',botSetupHelp:'Choose how the bot should speak to this business’s customers.',botNameAr:'Arabic bot name',botNameEn:'English bot name',botTone:'Tone',toneFriendly:'Friendly',toneProfessional:'Professional',toneLuxury:'Premium',toneConcise:'Concise',welcomeAr:'Optional Arabic welcome',welcomeEn:'Optional English welcome',languageChoiceHelp:'Every new customer is first asked to choose Arabic or English.'}
};
const t=k=>i18n[lang][k]||k;
function applyLanguage(){document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';$('langToggle').textContent=lang==='ar'?'EN':'ع';document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n));if(detail){renderServices();renderStaff();renderHours(detail.hours);renderOverview()} }
$('langToggle').onclick=()=>{lang=lang==='ar'?'en':'ar';localStorage.setItem('bookingLang',lang);applyLanguage()};
function toast(msg,error=false){let el=$('toast');el.textContent=msg;el.className='toast'+(error?' error':'');setTimeout(()=>el.classList.add('hidden'),2800);el.classList.remove('hidden')}

```


---

## whatsapp-bot/frontend/app-core.js

```javascript
async function api(path,opt={}){const r=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json',...(opt.headers||{})},...opt});if(r.status===401){showLogin();throw Error('unauthorized')}const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||d.error||r.statusText);return d}
function showLogin(){$('loginCard').classList.remove('hidden');$('app').classList.add('hidden');$('logout').classList.add('hidden')}
function showApp(){$('loginCard').classList.add('hidden');$('app').classList.remove('hidden');$('logout').classList.add('hidden')}
async function init(){applyLanguage();showApp();await loadBusinesses()}
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
let onboardingStep=1;
function setOnboardStep(step){
  onboardingStep=Math.max(1,Math.min(3,step));
  document.querySelectorAll('[data-onboard-step]').forEach(x=>x.classList.toggle('active',+x.dataset.onboardStep===onboardingStep));
  document.querySelectorAll('[data-onboard-dot]').forEach(x=>x.classList.toggle('active',+x.dataset.onboardDot<=onboardingStep));
  $('onboardBack').classList.toggle('hidden',onboardingStep===1);
  $('onboardNext').classList.toggle('hidden',onboardingStep===3);
  $('createBusiness').classList.toggle('hidden',onboardingStep!==3);
  const labels=lang==='ar'?['بيانات المنشأة','شخصية البوت','الخدمات']:['Business details','Bot personality','Services'];
  $('onboardStepLabel').textContent=labels[onboardingStep-1];
}
function validateOnboardStep(){
  if(onboardingStep===1){
    if(!$('nameAr').value.trim()||!$('nameEn').value.trim()||!normalizePhone($('phone').value)||!$('maps').value.trim())
      throw Error(lang==='ar'?'أكمل بيانات المنشأة المطلوبة.':'Complete the required business details.');
  }
  if(onboardingStep===3){
    let rows=[...document.querySelectorAll('#onboardingServices .onboardingServiceRow')];
    if(!rows.some(r=>r.querySelector('.o-ar').value.trim()&&r.querySelector('.o-en').value.trim()))
      throw Error(lang==='ar'?'أضف خدمة واحدة على الأقل.':'Add at least one service.');
  }
  return true;
}
$('onboardNext').onclick=()=>{try{validateOnboardStep();setOnboardStep(onboardingStep+1)}catch(e){toast(e.message,true)}};
$('onboardBack').onclick=()=>setOnboardStep(onboardingStep-1);

function resetBusinessDialog(){
  $('businessForm').reset();
  $('createMsg').textContent='';
  $('botTone').value='friendly';
  $('onboardingServices').innerHTML='';
  $('onboardingServices').appendChild(onboardingServiceRow({name_ar:'قص شعر',name_en:'Haircut',duration_min:30,price:60,buffer_min:10}));
  setOnboardStep(1);
}
$('openAddBusiness').onclick=$('emptyAddBusiness').onclick=()=>{resetBusinessDialog();$('businessDialog').showModal()};
$('addOnboardingService').onclick=()=>$('onboardingServices').appendChild(onboardingServiceRow());

function defaultHours(){let a=[];for(let ram of [false,true])for(let d=0;d<7;d++)a.push({day_of_week:d,open_time:'10:00',close_time:'22:00',is_closed:d===5,is_ramadan:ram});return a}
$('createBusiness').onclick=async()=>{let btn=$('createBusiness');try{validateOnboardStep();btn.disabled=true;btn.textContent=lang==='ar'?'جاري الإنشاء...':'Creating...';let sv=[...document.querySelectorAll('#onboardingServices .onboardingServiceRow')].map(r=>({name_ar:r.querySelector('.o-ar').value.trim(),name_en:r.querySelector('.o-en').value.trim(),duration_min:+r.querySelector('.o-duration').value,price:+r.querySelector('.o-price').value,buffer_min:+r.querySelector('.o-buffer').value})).filter(x=>x.name_ar&&x.name_en);if(!sv.length||sv.some(x=>!x.duration_min||x.duration_min<5||Number.isNaN(x.price)||x.price<0))throw Error(lang==='ar'?'تحقق من بيانات الخدمات.':'Check the service details.');let body={name_ar:$('nameAr').value.trim(),name_en:$('nameEn').value.trim(),phone:normalizePhone($('phone').value),maps_url:$('maps').value.trim(),latitude:null,longitude:null,vat_number:$('vat').value||null,cr_number:$('cr').value||null,bot_name_ar:$('botNameAr').value.trim()||null,bot_name_en:$('botNameEn').value.trim()||null,bot_tone:$('botTone').value,welcome_ar:$('welcomeAr').value.trim()||null,welcome_en:$('welcomeEn').value.trim()||null,services:sv,hours:defaultHours()};if(!body.name_ar||!body.name_en||!body.phone||!body.maps_url)throw Error(lang==='ar'?'أكمل الحقول المطلوبة.':'Complete all required fields.');let d=await api('/api/businesses',{method:'POST',body:JSON.stringify(body)});$('createMsg').innerHTML='<span class="ok">'+t('created')+'</span>';await loadBusinesses(d.id);if(d.qr)showQr(d.qr);setTimeout(()=>$('businessDialog').close(),600);toast(t('created'))}catch(e){$('createMsg').innerHTML='<span class="err">'+escapeHtml(e.message)+'</span>';toast(e.message,true)}finally{btn.disabled=false;btn.textContent=t('createConnect')}};
function normalizePhone(v){let p=v.replace(/\D/g,'');if(p.startsWith('05'))p='966'+p.slice(1);if(p.startsWith('5')&&p.length===9)p='966'+p;return p}
async function loadBusinesses(select){let rows=await api('/api/businesses');$('businessSelect').innerHTML=rows.map(x=>`<option value="${x.id}">${escapeHtml(lang==='ar'?x.name_ar:x.name_en)}</option>`).join('');if(select)$('businessSelect').value=select;if(rows.length){current=$('businessSelect').value;$('emptyState').classList.add('hidden');$('overviewContent').classList.remove('hidden');await loadDetail()}else{current=null;detail=null;$('emptyState').classList.remove('hidden');$('overviewContent').classList.add('hidden')}}
$('businessSelect').onchange=async()=>{current=$('businessSelect').value;await loadDetail()};
async function loadDetail(){if(!current)return;detail=await api('/api/businesses/'+current);renderServices();renderStaff();renderHours(detail.hours);renderSettings();renderProfile();await Promise.all([loadBookings(false),refreshConnection()]);renderOverview()}

```


---

## whatsapp-bot/frontend/app-admin.js

```javascript
function renderOverview(){if(!detail)return;let b=detail.business;$('heroBusinessName').textContent=lang==='ar'?b.name_ar:b.name_en;$('heroSub').textContent=(b.phone||'')+(b.maps_url?' · '+(lang==='ar'?'الموقع محفوظ':'Map saved'):'');$('servicesCount').textContent=(detail.services||[]).length;let now=new Date(),todayKey=dayKey(now);let active=appointmentsCache.filter(a=>a.status!=='cancelled');$('todayCount').textContent=active.filter(a=>dayKey(new Date(a.start_time))===todayKey).length;$('upcomingCount').textContent=active.filter(a=>new Date(a.start_time)>=now).length;let next=active.filter(a=>new Date(a.start_time)>=now).sort((a,b)=>new Date(a.start_time)-new Date(b.start_time)).slice(0,5);$('nextAppointments').innerHTML=next.length?next.map(a=>`<div class="appointmentItem"><div><strong>${escapeHtml(a.customer_name||a.customer_phone)}</strong><small>${escapeHtml(lang==='ar'?a.name_ar:a.name_en)} · ${formatDate(a.start_time)}</small></div><span class="pill">${escapeHtml(a.status)}</span></div>`).join(''):`<div class="emptyList">${t('noBookings')}</div>`}
async function refreshConnection(){if(!current)return;let badge=$('waBadge');badge.className='statusBadge waiting';badge.querySelector('b').textContent=t('checking');try{let d=await api(`/api/businesses/${current}/connection`);let state=((d.instance||d||{}).state||'').toLowerCase();let connected=['open','connected'].includes(state);let tested=false;if(connected){try{let s=await api(`/api/businesses/${current}/conversation-test-status`);tested=!!s.ok}catch{tested=false}}badge.className='statusBadge '+(connected?'connected':'offline');badge.querySelector('b').textContent=connected?t('connected'):t('notConnected');$('waChecklist').classList.toggle('done',connected);$('testChecklist').classList.toggle('done',tested);$('readyChecklist').classList.toggle('done',tested);$('waChecklist').querySelector('.check').textContent=connected?'✓':'2';$('testChecklist').querySelector('.check').textContent=tested?'✓':'3';$('readyChecklist').querySelector('.check').textContent=tested?'✓':'4';if(connected){$('qrWrap').classList.add('hidden');$('liveTestBox').classList.remove('hidden');await fillDefaultTestPhone()}else{$('liveTestBox').classList.add('hidden');await qr()}}catch{badge.className='statusBadge offline';badge.querySelector('b').textContent=t('notConnected');$('testChecklist').classList.remove('done');$('readyChecklist').classList.remove('done');await qr().catch(()=>{})}}
function showQr(q){if(!q)return;$('qrWrap').classList.remove('hidden');$('qr').src=q.startsWith('data:')?q:'data:image/png;base64,'+q}
async function qr(){if(!current)return;let d=await api(`/api/businesses/${current}/qr`);if(d.qr)showQr(d.qr)}
async function fillDefaultTestPhone(){
  try{
    if($('liveTestPhone').value)return;
    let d=await api('/api/client-defaults');
    if(d.test_phone)$('liveTestPhone').value=d.test_phone;
  }catch{}
}
$('refreshQr').onclick=async()=>{await qr();toast(lang==='ar'?'تم تحديث QR':'QR refreshed')};
$('sendLiveTest').onclick=async()=>{try{
  let phone=normalizePhone($('liveTestPhone').value);
  if(!phone)throw Error(lang==='ar'?'أدخل رقم اختبار صحيح.':'Enter a valid test number.');
  let d=await api(`/api/businesses/${current}/test-message`,{method:'POST',body:JSON.stringify({phone,language:$('liveTestLang').value})});
  $('liveTestResult').textContent=lang==='ar'?'تم الإرسال. رد الآن من واتساب ثم اضغط "تحقق من الرد".':'Sent. Reply from WhatsApp, then press "Check reply".';
  toast(lang==='ar'?'تم إرسال رسالة الاختبار':'Test message sent');
}catch(e){$('liveTestResult').textContent=e.message;toast(e.message,true)}};
$('checkLiveTest').onclick=async()=>{try{
  let d=await api(`/api/businesses/${current}/conversation-test-status`);
  if(d.ok){
    $('liveTestResult').textContent=(lang==='ar'?'تم استلام رد واتساب الحقيقي ✅ ':'Real WhatsApp reply received ✅ ')+(d.last_inbound_phone||'');
    $('testChecklist').classList.add('done');$('testChecklist').querySelector('.check').textContent='✓';$('readyChecklist').classList.add('done');$('readyChecklist').querySelector('.check').textContent='✓';toast(lang==='ar'?'اختبار واتساب مكتمل':'WhatsApp test complete');
  }else{
    $('liveTestResult').textContent=lang==='ar'?'لم يصل رد بعد. أرسل أي رسالة من رقم الاختبار.':'No reply received yet. Send any message from the test number.';
  }
}catch(e){toast(e.message,true)}};

$('refreshOverview').onclick=async()=>{await loadDetail();toast(t('saved'))};
function renderServices(){let box=$('serviceEditor');box.innerHTML='';(detail?.services||[]).forEach(s=>addServiceRow(s))}
function addServiceRow(s={}){let div=document.createElement('div');div.className='serviceRow';div.dataset.id=s.id||'';div.innerHTML=`<label><span>العربية</span><input value="${escapeAttr(s.name_ar||'')}" placeholder="قص شعر"></label><label><span>English</span><input value="${escapeAttr(s.name_en||'')}" placeholder="Haircut" dir="ltr"></label><label><span>${t('duration')} (${t('minutes')})</span><input type="number" min="1" value="${s.duration_min||30}"></label><label><span>${t('price')} (${t('sar')})</span><input type="number" min="0" step="0.01" value="${s.price||0}"></label><label><span>${t('buffer')} (${t('minutes')})</span><input type="number" min="0" value="${s.buffer_min||0}"></label><button class="deleteBtn" type="button" title="${t('delete')}">×</button>`;div.querySelector('.deleteBtn').onclick=()=>div.remove();box.appendChild(div)}
$('addService').onclick=()=>addServiceRow();
$('saveServices').onclick=async()=>{try{let items=[...document.querySelectorAll('.serviceRow')].map(r=>{let i=r.querySelectorAll('input');return{id:r.dataset.id||null,name_ar:i[0].value,name_en:i[1].value,duration_min:+i[2].value,price:+i[3].value,buffer_min:+i[4].value}}).filter(x=>x.name_ar&&x.name_en);if(!items.length)throw Error(lang==='ar'?'أضف خدمة واحدة على الأقل.':'Add at least one service.');await api(`/api/businesses/${current}/services`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
const dayNames={ar:['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'],en:['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']};
function renderHours(items){let map=new Map((items||[]).map(h=>[`${h.is_ramadan}-${h.day_of_week}`,h]));let box=$('hoursEditor');box.innerHTML='';for(let ram of [false,true]){let group=document.createElement('div');group.className='hourGroup '+((ram&&hoursMode==='ramadan')||(!ram&&hoursMode==='normal')?'active':'');group.dataset.group=ram?'ramadan':'normal';for(let d=0;d<7;d++){let x=map.get(`${ram}-${d}`)||{day_of_week:d,open_time:'10:00',close_time:'22:00',is_closed:false,is_ramadan:ram};let div=document.createElement('div');div.className='hourRow';div.dataset.day=d;div.dataset.ramadan=ram;div.innerHTML=`<span class="dayName">${dayNames[lang][d]}</span><input type="time" value="${(x.open_time||'10:00').slice(0,5)}"><input type="time" value="${(x.close_time||'22:00').slice(0,5)}"><label class="closedLabel"><input type="checkbox" ${x.is_closed?'checked':''}> ${t('closed')}</label>`;group.appendChild(div)}box.appendChild(group)}}
document.querySelectorAll('[data-hours-mode]').forEach(b=>b.onclick=()=>{hoursMode=b.dataset.hoursMode;document.querySelectorAll('[data-hours-mode]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.hourGroup').forEach(x=>x.classList.toggle('active',x.dataset.group===hoursMode))});

```


---

## whatsapp-bot/frontend/app-settings.js

```javascript

function renderStaff(){
  let box=$('staffEditor'); if(!box)return; box.innerHTML='';
  (detail?.staff||[]).forEach(s=>addStaffRow(s));
}
function addStaffRow(s={}){
  let div=document.createElement('div'); div.className='staffRow'; div.dataset.id=s.id||'';
  div.innerHTML=`<label><span>${lang==='ar'?'العربية':'Arabic'}</span><input class="st-ar" value="${escapeAttr(s.name_ar||'')}" placeholder="محمد"></label><label><span>English</span><input class="st-en" dir="ltr" value="${escapeAttr(s.name_en||'')}" placeholder="Mohammed"></label><label class="staffActive"><input class="st-active" type="checkbox" ${s.is_active===false?'':'checked'}> ${t('active')}</label><button class="deleteBtn staffDelete" type="button" title="${t('delete')}">×</button>`;
  div.querySelector('.staffDelete').onclick=()=>{div.querySelector('.st-active').checked=false;div.classList.add('hidden')};
  $('staffEditor').appendChild(div);
}
$('addStaff').onclick=()=>addStaffRow();
$('saveStaff').onclick=async()=>{
  try{
    let items=[...document.querySelectorAll('#staffEditor .staffRow')].map(r=>({id:r.dataset.id||null,name_ar:r.querySelector('.st-ar').value.trim(),name_en:r.querySelector('.st-en').value.trim(),is_active:r.querySelector('.st-active').checked})).filter(x=>x.name_ar&&x.name_en);
    if(!items.some(x=>x.is_active))throw Error(lang==='ar'?'يجب أن يكون هناك موظف نشط واحد على الأقل.':'At least one active staff member is required.');
    await api(`/api/businesses/${current}/staff`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'));
  }catch(e){toast(e.message,true)}
};

function renderProfile(){
  if(!detail?.business)return; let b=detail.business;
  $('profileNameAr').value=b.name_ar||''; $('profileNameEn').value=b.name_en||''; $('profilePhone').value=b.phone||'';
  $('profileMaps').value=b.maps_url||''; $('profileVat').value=b.vat_number||''; $('profileCr').value=b.cr_number||'';
}
$('saveProfile').onclick=async()=>{
  try{
    let b=detail.business;
    let body={name_ar:$('profileNameAr').value.trim(),name_en:$('profileNameEn').value.trim(),phone:normalizePhone($('profilePhone').value),maps_url:$('profileMaps').value.trim(),latitude:b.latitude,longitude:b.longitude,vat_number:$('profileVat').value.trim()||null,cr_number:$('profileCr').value.trim()||null};
    if(!body.name_ar||!body.name_en||!body.phone||!body.maps_url)throw Error(lang==='ar'?'أكمل الحقول المطلوبة.':'Complete all required fields.');
    await api(`/api/businesses/${current}/profile`,{method:'PUT',body:JSON.stringify(body)});await loadBusinesses(current);toast(t('saved'));
  }catch(e){toast(e.message,true)}
};

$('saveHours').onclick=async()=>{try{let items=[...document.querySelectorAll('.hourRow')].map(r=>{let i=r.querySelectorAll('input');return{day_of_week:+r.dataset.day,open_time:i[0].value,close_time:i[1].value,is_closed:i[2].checked,is_ramadan:r.dataset.ramadan==='true'}});await api(`/api/businesses/${current}/hours`,{method:'PUT',body:JSON.stringify(items)});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
function renderSettings(){let s=detail?.settings||{};$('ramadanMode').checked=s.ramadan_mode==='true';$('prayerEnabled').checked=s.prayer_buffer_enabled==='true';$('prayerBuffer').value=s.prayer_buffer_min||30;$('slotInterval').value=s.slot_interval_min||30;$('cancelAr').value=s.cancellation_policy_ar||'';$('cancelEn').value=s.cancellation_policy_en||'';$('settingsBotNameAr').value=s.bot_name_ar||detail?.business?.name_ar||'';$('settingsBotNameEn').value=s.bot_name_en||detail?.business?.name_en||'';$('settingsBotTone').value=s.bot_tone||'friendly';$('settingsWelcomeAr').value=s.welcome_ar||'';$('settingsWelcomeEn').value=s.welcome_en||''}
$('saveSettings').onclick=async()=>{try{let values={ramadan_mode:String($('ramadanMode').checked),prayer_buffer_enabled:String($('prayerEnabled').checked),prayer_buffer_min:$('prayerBuffer').value,slot_interval_min:$('slotInterval').value,cancellation_policy_ar:$('cancelAr').value,cancellation_policy_en:$('cancelEn').value,bot_name_ar:$('settingsBotNameAr').value.trim(),bot_name_en:$('settingsBotNameEn').value.trim(),bot_tone:$('settingsBotTone').value,welcome_ar:$('settingsWelcomeAr').value.trim(),welcome_en:$('settingsWelcomeEn').value.trim(),language_prompt_enabled:'true'};await api(`/api/businesses/${current}/settings`,{method:'PUT',body:JSON.stringify({values})});await loadDetail();toast(t('saved'))}catch(e){toast(e.message,true)}};
$('loadBookings').onclick=()=>loadBookings(true);
async function loadBookings(showToast=false){if(!current)return;appointmentsCache=await api(`/api/businesses/${current}/appointments`);$('bookingRows').innerHTML=appointmentsCache.length?appointmentsCache.map(a=>`<tr><td>${escapeHtml(a.customer_name||'-')}</td><td dir="ltr">${escapeHtml(a.customer_phone)}</td><td>${escapeHtml(lang==='ar'?a.name_ar:a.name_en)}</td><td>${escapeHtml(lang==='ar'?a.staff_ar:a.staff_en)}</td><td>${formatDate(a.start_time)}</td><td><span class="pill">${escapeHtml(a.status)}</span></td></tr>`).join(''):`<tr><td colspan="6"><div class="emptyList">${t('noBookings')}</div></td></tr>`;renderOverview();if(showToast)toast(t('saved'))}
function formatDate(v){try{return new Intl.DateTimeFormat(lang==='ar'?'ar-SA':'en-GB',{weekday:'short',day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Asia/Riyadh'}).format(new Date(v))}catch{return v}}
function dayKey(d){return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Riyadh'}).format(d)}
function escapeHtml(v=''){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function escapeAttr(v=''){return escapeHtml(v)}
init();

```


---

## whatsapp-bot/migrations/001_init.sql

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY,
    "businessId" UUID NOT NULL UNIQUE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    phone TEXT NOT NULL,
    whatsapp_session_id TEXT NOT NULL UNIQUE,
    maps_url TEXT NOT NULL,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    vat_number TEXT,
    cr_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT businesses_tenant_identity CHECK (id = "businessId")
);

CREATE TABLE IF NOT EXISTS services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0 AND duration_min <= 1440),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    buffer_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_min >= 0 AND buffer_min <= 240)
);

CREATE TABLE IF NOT EXISTS working_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    is_ramadan BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT working_hours_times CHECK (
        is_closed OR (open_time IS NOT NULL AND close_time IS NOT NULL AND close_time > open_time)
    ),
    UNIQUE ("businessId", day_of_week, is_ramadan)
);

CREATE TABLE IF NOT EXISTS staff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    name_ar TEXT NOT NULL,
    name_en TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    customer_phone TEXT NOT NULL,
    service_id UUID NOT NULL REFERENCES services(id),
    staff_id UUID NOT NULL REFERENCES staff(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('confirmed','rescheduled','cancelled','completed','no_show')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reminder_24_sent BOOLEAN NOT NULL DEFAULT FALSE,
    reminder_2_sent BOOLEAN NOT NULL DEFAULT FALSE,
    followup_sent BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT appointment_time_order CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    phone TEXT NOT NULL,
    name TEXT,
    no_show_count INTEGER NOT NULL DEFAULT 0 CHECK (no_show_count >= 0),
    last_visit TIMESTAMPTZ,
    UNIQUE ("businessId", phone)
);

CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "businessId" UUID NOT NULL REFERENCES businesses("businessId") ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE ("businessId", key)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'appointments_no_overlap'
    ) THEN
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (
            "businessId" WITH =,
            staff_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        ) WHERE (status IN ('confirmed','rescheduled'));
    END IF;
END $$;

```


---

## whatsapp-bot/migrations/002_indexes.sql

```sql
CREATE INDEX IF NOT EXISTS idx_services_business ON services("businessId");
CREATE INDEX IF NOT EXISTS idx_hours_business_day ON working_hours("businessId", day_of_week, is_ramadan);
CREATE INDEX IF NOT EXISTS idx_staff_business_active ON staff("businessId", is_active);
CREATE INDEX IF NOT EXISTS idx_appointments_business_start ON appointments("businessId", start_time);
CREATE INDEX IF NOT EXISTS idx_appointments_business_phone ON appointments("businessId", customer_phone, start_time);
CREATE INDEX IF NOT EXISTS idx_customers_business_phone ON customers("businessId", phone);
CREATE INDEX IF NOT EXISTS idx_settings_business_key ON settings("businessId", key);

```


---

## whatsapp-bot/migrations/003_customer_language.sql

```sql
ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS preferred_language TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='customers_preferred_language_check'
  ) THEN
    ALTER TABLE customers
      ADD CONSTRAINT customers_preferred_language_check
      CHECK (preferred_language IS NULL OR preferred_language IN ('ar','en'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_customers_business_language
  ON customers("businessId", preferred_language);

```
