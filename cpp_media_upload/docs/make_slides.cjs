// Optional presentation source (not part of the C++ application).
// Requires Node.js and globally installed pptxgenjs.
const pptxgen = require('pptxgenjs');
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'MediaDock Project';
pptx.subject = 'C++20 Distributed Producer–Consumer Media Upload System';
pptx.title = 'MediaDock — Architecture and Implementation';
pptx.lang = 'en-US';
pptx.theme = { headFontFace:'Aptos Display', bodyFontFace:'Aptos', lang:'en-US' };
const SW=13.333, SH=7.5;
const C={navy:'101823',surface:'1C2937',blue:'57A4FB',cyan:'7DDDEB',white:'F5F8FC',muted:'AEBCCB',yellow:'F8C56E',green:'79D7AD',red:'E98792',line:'34465B'};
let page=0;
function shape(s, type,x,y,w,h,fill=C.surface,line=C.line,radius){s.addShape(type,{x,y,w,h,rectRadius:radius,fill:{color:fill},line:{color:line,width:0.6}});}
function text(s, str, x,y,w,h, opts={}){s.addText(str,{x,y,w,h,color:C.white,fontFace:'Aptos',fontSize:17,margin:0,breakLine:false,fit:'shrink',valign:'mid',...opts});}
function base(title,subtitle){const s=pptx.addSlide();page++;s.background={color:C.navy};s.addShape(pptx.ShapeType.rect,{x:0,y:0,w:SW,h:.09,line:{color:C.blue},fill:{color:C.blue}});text(s,'MEDIADOCK  /  C++ DISTRIBUTED UPLOAD LAB',.63,.28,8,.30,{fontSize:10,color:C.cyan,bold:true,charSpacing:2});text(s,title,.63,.87,12.0,.78,{fontSize:33,bold:true});if(subtitle)text(s,subtitle,.65,1.63,11.95,.53,{fontSize:15,color:C.muted});text(s,`2026  •  Architecture / implementation  •  ${String(page).padStart(2,'0')}`,.65,7.06,12.2,.22,{fontSize:10,color:'718398'});return s;}
function box(s,x,y,w,h,title,detail,color=C.blue){shape(s,pptx.ShapeType.roundRect,x,y,w,h);s.addShape(pptx.ShapeType.rect,{x:x+.01,y:y+.18,w:.045,h:h-.36,line:{color},fill:{color}});text(s,title,x+.24,y+.20,w-.43,.39,{fontSize:16,bold:true});text(s,detail,x+.24,y+.70,w-.48,h-.88,{fontSize:12,color:C.muted,valign:'top',breakLine:false});}
function bullet(s,items,x,y,w,{size=17,gap=.72,color=C.white}={}) {items.forEach((a,i)=>{text(s,'•',x,y+i*gap,.24,.35,{fontSize:size+2,color:C.blue,bold:true});text(s,a,x+.35,y+i*gap,w-.35,.52,{fontSize:size,color});});}
function arrow(s,x,y,d='→',color=C.cyan){text(s,d,x,y,.5,.38,{fontSize:24,color,bold:true,align:'center'});}
function pill(s,str,x,y,w,color=C.blue){shape(s,pptx.ShapeType.roundRect,x,y,w,.44,'263D56','405B78');text(s,str,x+.14,y+.04,w-.28,.35,{fontSize:12,bold:true,color});}

{const s=base('Distributed Media Upload Service','A C++20 producer–consumer application across two virtual machines');
text(s,'C++20  •  gRPC  •  Bounded FIFO  •  Drogon  •  SQLite  •  FFmpeg',.67,2.38,12,.5,{fontSize:19,color:C.cyan});
box(s,.68,3.30,5.62,2.17,'VM 1  /  PRODUCER','p threads read from p distinct video folders and stream binary chunks using gRPC.',C.blue);
box(s,7.03,3.30,5.62,2.17,'VM 2  /  CONSUMER','Receive, queue, process, save, and serve videos in a browser gallery.',C.green);
arrow(s,6.39,4.24);
text(s,'Core features + all three bonuses planned and implemented in source.',.67,6.25,11.6,.34,{fontSize:16,color:C.muted});}
{const s=base('Assignment requirements','A correct submission demonstrates both functionality and concurrency concepts.');
box(s,.67,2.25,3.81,3.46,'Inputs','p = producer threads\nc = consumer worker threads\nq = waiting queue capacity',C.blue);
box(s,4.76,2.25,3.81,3.46,'Outputs','Consumer GUI\n10-second hover preview\nFull video on click',C.green);
box(s,8.85,2.25,3.81,3.46,'Bonuses','Queue-full notification\nSHA-256 duplicate detection\nOptional video compression',C.yellow);
text(s,'Key constraint: producer and consumer run on separate virtual machines and communicate over gRPC.',.71,6.22,11.8,.51,{fontSize:16,color:C.cyan});}
{const s=base('Two-VM architecture','Logical processing flow and protocol boundaries.');
box(s,.70,2.35,2.58,2.23,'Producer threads','p source folders\nChunked RPC streams',C.blue);
arrow(s,3.42,3.18);
box(s,4.06,2.35,2.60,2.23,'gRPC receiver','Private disk spool\nSHA-256 hash',C.cyan);
arrow(s,6.79,3.18);
box(s,7.41,2.35,2.13,2.23,'FIFO queue','q waiting jobs\nDrop newest on full',C.yellow);
arrow(s,9.69,3.18);
box(s,10.28,2.35,2.34,2.23,'c workers','FFmpeg pipeline\nPublish READY',C.green);
shape(s,pptx.ShapeType.roundRect,3.85,5.27,5.63,.83,'243342','486783');text(s,'SQLite metadata + uploads/ + previews/',4.15,5.49,5.1,.34,{fontSize:15,bold:true,align:'center'});
text(s,'HTTP gallery: Drogon API + HTML / CSS / JavaScript',3.73,6.31,6,.36,{fontSize:15,color:C.cyan,align:'center'});}
{const s=base('Technology decisions','Chosen for explicit concurrency, educational clarity and reproducible Linux builds.');
const rows=[['Language','C++20'],['RPC','gRPC C++ + Protocol Buffers'],['Threads / queue','std::jthread, mutex, condition_variable, deque'],['Browser backend','Drogon HTTP + JSON'],['Frontend','Vanilla HTML / CSS / JavaScript'],['Media','FFmpeg + ffprobe'],['Database / dedupe','SQLite + OpenSSL SHA-256'],['Build / deployment','CMake + Ninja; two Linux VMs']];
rows.forEach((r,i)=>{const y=2.14+i*.49;shape(s,pptx.ShapeType.rect,.75,y,11.8,.43,i%2?'1A2835':'223245',i%2?'1A2835':'223245');text(s,r[0],1.02,y+.06,3.0,.3,{fontSize:14,color:C.cyan,bold:true});text(s,r[1],4.11,y+.05,8.0,.32,{fontSize:14});});}
{const s=base('gRPC upload lifecycle','Transport success and application acceptance are separate concepts.');
const xs=[.68,3.20,5.72,8.24,10.76],names=['METADATA','CHUNKS','TEMP FILE','ADMISSION','REPLY'];
names.forEach((n,i)=>{box(s,xs[i],2.44,2.00,1.75,n,['ID, producer, size','64KiB payloads','Disk + SHA-256','Hash + q check','QUEUED / FULL'][i],i===3?C.yellow:C.blue);if(i<4)arrow(s,xs[i]+2.05,3.05);});
box(s,1.05,4.95,5.38,1.03,'Normal','Accepted for asynchronous worker processing',C.green);
box(s,6.83,4.95,5.38,1.03,'Alternatives','QUEUE_FULL · DUPLICATE · INVALID_FILE · SERVER_BUSY',C.red);
text(s,'QUEUED is not the same as READY: worker processing may still fail.',1.04,6.42,11,.36,{color:C.yellow,fontSize:15,bold:true});}
{const s=base('Producer design','Exactly p C++ threads, one unique folder per worker.');
for(let i=0;i<3;i++){box(s,.75+i*4.22,2.40,3.76,2.0,`Producer ${i===2?'p':i+1}`,`Folder producer_${i===2?'p':i+1}/\nReads in filename order\nUploads files sequentially per thread`,C.blue);}
text(s,'All p workers run concurrently; large files are streamed instead of loaded into RAM.',.78,5.14,11.7,.52,{fontSize:18,color:C.cyan});
text(s,'Stable logical IDs help recognize a previously accepted upload after a lost response.',.78,5.89,11.6,.40,{fontSize:15,color:C.muted});}
{const s=base('Bounded queue semantics','q counts waiting jobs only; active workers are outside the waiting buffer.');
pill(s,'p = 4',.85,2.27,1.45,C.blue);pill(s,'c = 2',2.57,2.27,1.45,C.green);pill(s,'q = 3',4.29,2.27,1.45,C.yellow);
text(s,'Actively processing',.85,3.02,4.0,.31,{fontSize:15,bold:true});
box(s,.88,3.47,2.35,1.15,'Worker 1','Video A',C.green);box(s,3.46,3.47,2.35,1.15,'Worker 2','Video B',C.green);
text(s,'Waiting queue (FULL)',6.34,3.02,6,.31,{fontSize:15,bold:true});
['Video C','Video D','Video E'].forEach((n,i)=>box(s,6.36+i*2.10,3.47,1.85,1.15,n,`Slot ${i+1}`,C.blue));
text(s,'Incoming Video F → dropped on arrival; producer receives QUEUE_FULL.',1.04,5.43,11.5,.45,{fontSize:18,color:C.red,bold:true});
text(s,'FIFO refers to dequeue order; different worker durations may change completion order.',1.04,6.10,11.4,.45,{fontSize:14,color:C.muted});}
{const s=base('Synchronization mechanisms','Shared-state correctness is the center of this assignment.');
box(s,.69,2.20,5.83,1.55,'Queue mutex','Atomically check size, add/remove jobs; protect FIFO state.',C.blue);
box(s,6.76,2.20,5.83,1.55,'Condition variable','Consumer workers sleep when no job is available.',C.cyan);
box(s,.69,4.10,5.83,1.55,'Admission mutex + SQLite UNIQUE','Prevent double claim of final queue slot or SHA-256 content.',C.yellow);
box(s,6.76,4.10,5.83,1.55,'Semaphore + bounded threads','Separately cap active uploads and concurrent consumers.',C.green);}
{const s=base('Storage and lifecycle','Files move through private temporary storage before publication.');
const states=['RECEIVING','QUEUED','PROCESSING','READY'];states.forEach((n,i)=>{pill(s,n,.77+i*3.14,2.32,2.72,i===3?C.green:C.cyan);if(i<3)arrow(s,3.57+i*3.14,2.32);});
box(s,.72,3.44,3.67,2.06,'incoming/','Partial transfers, original temp files, staged processing output.',C.yellow);
box(s,4.80,3.44,3.67,2.06,'uploads/','One final folder containing READY full-length video MP4 files.',C.blue);
box(s,8.88,3.44,3.67,2.06,'previews/ + SQLite','Derived 10-sec clips, thumbnails, states, hash uniqueness.',C.green);
text(s,'The database is only marked READY after all required playback assets exist.',.85,6.09,11.7,.47,{fontSize:16,color:C.cyan});}
{const s=base('Three bonus features','Designed into the basic data model and upload interface.');
box(s,.68,2.34,3.82,3.27,'1  Queue-full response','Reply QUEUE_FULL after transfer if all q waiting slots are occupied. Producer logs outcome.',C.yellow);
box(s,4.75,2.34,3.82,3.27,'2  Duplicate detection','Hash original bytes via SHA-256; enforce unique accepted hash claims in SQLite.',C.blue);
box(s,8.82,2.34,3.82,3.27,'3  Compression','Optional FFmpeg H.264/AAC transcode; use smaller playable output when beneficial.',C.green);
text(s,'Planned extension (not built): admission reservation BEFORE transferring full bytes.',.74,6.13,11.7,.43,{fontSize:14,color:C.muted});}
{const s=base('Browser gallery','C++ Drogon server: ordinary HTTP for users, gRPC only for producer uploads.');
box(s,.76,2.34,5.74,3.18,'Hover preview','• Generated muted H.264 preview MP4\n• Maximum 10 seconds\n• Reset on mouse exit\n• Browser-safe autoplay',C.blue);
box(s,6.79,2.34,5.74,3.18,'Full playback','• Click thumbnail to open player\n• Browser HTML5 video controls\n• HTTP 206 byte-range support\n• Seek, pause, replay',C.green);
text(s,'HTTP API: /api/videos, /api/stats, /api/videos/{id}/stream, /preview, /thumbnail',.78,6.04,11.7,.43,{fontSize:15,color:C.cyan});}
{const s=base('Verification status','What is tested now, and what remains to do before demonstration.');
box(s,.71,2.34,5.72,3.53,'PASS — tested in this environment','• Bounded queue + multithread accounting\n• SHA-256 and SQLite uniqueness\n• FFmpeg synthetic media pipeline\n• READY video + JPEG + 10-sec preview\n• Browser JavaScript syntax',C.green);
box(s,6.80,2.34,5.72,3.53,'PENDING — requires full VM setup','• Full gRPC + Drogon compilation\n• Two-VM uploads and concurrency\n• HTTP byte ranges and browser seeking\n• Concurrent overflow/dedupe integration\n• Restart and interruption tests',C.yellow);
text(s,'Do not claim a complete system acceptance test before actually running these cases.',.87,6.26,11.4,.42,{fontSize:15,color:C.red,bold:true});}
{const s=base('Deliverables and next milestones','Use this deck as an editable starting point; replace pending results with actual evidence.');
bullet(s,['Source code + CMake + Protocol Buffers contracts','Build, VM setup and operating instructions','Repeatable core tests and full system test matrix','Recorded two-VM demonstration (still required)','Slides: architecture, queue, synchronization, test results'],1.02,2.43,11.1,{size:19,gap:.77});
text(s,'Next: install VM dependencies → build full app → run cross-VM tests → record demo.',1.02,6.45,11.2,.41,{fontSize:15,color:C.cyan,bold:true});}

pptx.writeFile({fileName: require('path').join(__dirname,'MediaDock_Presentation.pptx')});
