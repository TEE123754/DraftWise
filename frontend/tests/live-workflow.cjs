const {chromium}=require('@playwright/test');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://localhost:3000/demo');
  await page.getByRole('button',{name:'Start the demo'}).click();
  await page.getByRole('heading',{name:'Overview',exact:true}).waitFor({timeout:90000});
  await page.getByRole('link',{name:'Inbox',exact:true}).click();
  await page.getByRole('button',{name:'Simulate Gmail fetch'}).click();
  await page.getByRole('link',{name:'Open document comparison'}).waitFor({timeout:180000});
  await page.getByRole('region',{name:'Email review workflow'}).getByText('checked',{exact:true}).waitFor({timeout:90000});
  const email=await page.evaluate(async()=>{
   const id=location.pathname.split('/').at(-1);
   const r=await fetch(`http://localhost:8000/api/v1/emails/${id}`,{credentials:'include',headers:{'X-Demo-Mode':'true','X-Workspace-Id':sessionStorage.getItem('draftwise-demo-workspace')}});
   return r.json();
  });
  if(email.workflow.state!=='checked')throw Error('Workflow not checked: '+email.workflow.state);
  if(email.attachments.length!==2||email.extractions.length!==2)throw Error('Missing linked documents');
  fs.mkdirSync('../artifacts/ui',{recursive:true});
  await page.screenshot({path:'../artifacts/ui/workflow-email-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Email mobile overflow');
  await page.screenshot({path:'../artifacts/ui/workflow-email-mobile.png',fullPage:true});
  await page.getByRole('link',{name:'Open document comparison'}).click();
  await page.getByRole('heading',{name:'email_001',exact:true}).waitFor();
  await page.getByRole('button',{name:'End demo',exact:true}).click();
  if(errors.length)throw Error(errors.join('; '));
  const result={state:email.workflow.state,category:email.classification.category,classification:email.classification.run_metadata,extractionMethods:email.extractions.map(x=>({method:x.run_metadata.method,fallback_reason:x.run_metadata.fallback_reason})),attachments:email.attachments.map(x=>x.original_name)};
  fs.mkdirSync('../artifacts/quality',{recursive:true});
  fs.writeFileSync('../artifacts/quality/live-workflow.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify({state:result.state,category:result.category,classificationMethod:result.classification.method,fallback:result.classification.fallback_reason,extractionMethods:result.extractionMethods}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
