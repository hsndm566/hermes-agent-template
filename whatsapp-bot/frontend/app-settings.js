
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
