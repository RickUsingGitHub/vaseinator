// Shared Python owns library validation, profiles, locks and restoration; this file only presents them.
export function libraryDialog({read, command, current, exportFile, importFile}) {
  const dlg = document.createElement('dialog');
  dlg.className = 'library';
  const title = document.createElement('h2'); title.textContent = 'Design library and profiles'; dlg.append(title);
  const help = document.createElement('p');
  help.textContent = 'Saved in this browser. Export a library backup to transfer it to desktop or another browser. Recovery keeps the last 30 settled designs. Thumbnails are silhouette sketches.';
  dlg.append(help);
  const locks = document.createElement('div'); dlg.append(locks);
  const content = document.createElement('div'); dlg.append(content);
  const footer = document.createElement('div'); dlg.append(footer);
  function button(parent, label, work) {
    const b=document.createElement('button'); b.textContent=label; parent.append(b);
    b.addEventListener('click',async()=>{b.disabled=true;try{await work();}finally{b.disabled=false;}});return b;
  }
  button(footer,'Export library backup',exportFile);
  button(footer,'Import library',()=>importFile(refresh));
  button(footer,'Close',()=>dlg.close());
  dlg.addEventListener('close',()=>dlg.remove());
  async function refresh() {
    const data = await read();
    locks.replaceChildren(); content.replaceChildren();
    const label=document.createElement('p');label.textContent='Keep these when using Surprise me (printer settings are always kept):';locks.append(label);
    for(const name of data.locks){
      const lab=document.createElement('label'), input=document.createElement('input');input.type='checkbox';input.checked=data.workspace.locks.includes(name);
      lab.append(input,document.createTextNode(name)); locks.append(lab);
      input.addEventListener('change',async()=>{const selected=[...locks.querySelectorAll('label')].filter(l=>l.firstChild.checked).map(l=>l.textContent);await command('locks',{locks:selected});});
    }
    for(const [category,title] of [['designs','My designs'],['profiles','Printer and material profiles'],['recovery','Recovery']]){
      const section=document.createElement('section');content.append(section);
      const heading=document.createElement('h3');heading.textContent=title;section.append(heading);
      async function save(kind){const name=prompt('Name for this saved entry:',current().name);if(name?.trim()){await command('save',{category,name,kind});await refresh();}}
      if(category==='designs')button(section,'Save current variant',()=>save('printer'));
      if(category==='profiles'){button(section,'Save printer',()=>save('printer'));button(section,'Save material',()=>save('material'));}
      const entries=[...data.workspace[category]].sort((a,b)=>Number(b.favorite)-Number(a.favorite)||b.created.localeCompare(a.created));
      if(!entries.length){const p=document.createElement('p');p.textContent='No saved entries yet.';section.append(p);}
      for(const e of entries){
        const row=document.createElement('div');row.className='library-entry';section.append(row);
        if(category==='designs'){const img=document.createElement('img');img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(data.thumbnails[e.id]);img.alt='Silhouette sketch';row.append(img);}
        const label=document.createElement('span');label.textContent=(e.favorite?'★ ':'')+(category==='profiles'?e.kind+': ':'')+e.name+' — '+new Date(e.created).toLocaleString();row.append(label);
        button(row,category==='profiles'?'Apply':'Restore',async()=>{await command('restore',{category,id:e.id});await refresh();});
        if(category==='designs')button(row,e.favorite?'Unfavourite':'Favourite',async()=>{await command('favorite',{id:e.id});await refresh();});
        button(row,'Remove',async()=>{if(confirm('Remove this saved entry?')){await command('delete',{category,id:e.id});await refresh();}});
      }
    }
  }
  document.body.append(dlg);dlg.showModal();refresh();
}
