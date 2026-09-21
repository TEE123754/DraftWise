const {chromium}=require('@playwright/test');
const fs=require('node:fs');
(async()=>{const b=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await b.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://localhost:3000/demo');await page.getByRole('button',{name:'Start the demo'}).click();
 await page.getByRole('heading',{name:'Overview',exact:true}).waitFor({timeout:90000});
 const result=await page.evaluate(async()=>{
  const headers={'X-Demo-Mode':'true','X-Workspace-Id':sessionStorage.getItem('draftwise-demo-workspace'),'Content-Type':'application/json','Idempotency-Key':crypto.randomUUID()};
  async function call(path,method='GET',body){const r=await fetch('http://localhost:8000/api/v1'+path,{method,headers,credentials:'include',body:body?JSON.stringify(body):undefined});if(!r.ok)throw Error(path+': '+r.status);return r.json();}
  const missing=(await call('/emails?state=waiting_for_draft&limit=1')).items[0];
  const actions=await call(`/emails/${missing.id}/document-actions`);if(!actions.can_request||!actions.missing.length)throw Error('Missing-document action absent');
  const spam=(await call('/emails?category=SPAM&limit=1')).items[0];
  await call('/emails/trash','POST',{email_ids:[spam.id],reason:'Local acceptance check: reviewed spam'});
  if(!(await call('/emails?trash=true')).items.some(x=>x.id===spam.id))throw Error('Trash missing');
  await call(`/emails/${spam.id}/restore`,'POST',{reason:'Restore after local acceptance check'});
  const restored=await call(`/emails/${spam.id}`);if(!restored.id)throw Error('Restore failed');
  const alert=(await call('/alerts')).items.find(x=>['open','acknowledged'].includes(x.lifecycle));
  if(alert)await call(`/alerts/${alert.id}/action`,'POST',{action:'investigate',reason:'Local check: reviewed source evidence'});
  return {missing:actions.missing,action:actions.kind,trashRestore:true,alertInvestigated:!!alert,emailId:missing.id,aiRequested:false};
 });
 await page.goto('http://localhost:3000/inbox/'+result.emailId);await page.getByRole('region',{name:'Document follow-up'}).getByText('Draft a reply to the sender',{exact:true}).waitFor({timeout:30000});
 await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
 await page.goto('http://localhost:3000/trash');await page.getByRole('heading',{name:'Trash',exact:true}).waitFor();
 if(errors.length)throw Error(errors.join('; '));fs.writeFileSync('../artifacts/p4-p6-live.json',JSON.stringify({...result,browserErrors:errors,mobileOverflow:false},null,2));console.log(JSON.stringify(result));
 await page.getByRole('button',{name:'End demo',exact:true}).click();
}finally{await b.close();}})().catch(e=>{console.error(e.message);process.exitCode=1});
