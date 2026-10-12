const esc=(s:string)=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const inline=(s:string):string=>esc(s)
 .replace(/`([^`]+)`/g,'<code>$1</code>')
 .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
 .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g,'<em>$1</em>')
 .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

// Une ligne de tableau GFM : au moins un `|`, pas vide une fois les pipes
// de bord retirés. La ligne de séparation (`|---|:--:|`) ne sert qu'à
// reconnaître un tableau — l'alignement par colonne n'est pas repris.
const parseRow=(line:string):string[]=>{
 let s=line.trim();
 if(s.startsWith('|'))s=s.slice(1);
 if(s.endsWith('|'))s=s.slice(0,-1);
 return s.split('|').map(c=>c.trim());
};
const isSeparatorRow=(line:string):boolean=>{
 const cells=parseRow(line);
 return cells.length>0&&cells.every(c=>/^:?-{1,}:?$/.test(c));
};

// Rendu minimal, sans dépendance (le projet n'en a aucune en exécution) :
// code fences, titres, listes, citations, tableaux, gras/italique/code/liens
// en ligne. Pas un CommonMark complet — juste de quoi afficher proprement ce
// qu'Axon écrit (ses résumés multi-lignes arrivent souvent en tableau).
export function renderMarkdown(text:string):string{
 const lines=text.replace(/\r\n/g,'\n').split('\n');
 const out:string[]=[];
 let i=0,para:string[]=[],list:{tag:'ul'|'ol';items:string[]}|null=null,quote:string[]|null=null;
 const flushPara=()=>{if(para.length){out.push(`<p>${para.map(inline).join('<br>')}</p>`);para=[];}};
 const flushList=()=>{if(list){out.push(`<${list.tag}>${list.items.map(it=>`<li>${inline(it)}</li>`).join('')}</${list.tag}>`);list=null;}};
 const flushQuote=()=>{if(quote){out.push(`<blockquote>${quote.map(inline).join('<br>')}</blockquote>`);quote=null;}};
 while(i<lines.length){
  const line=lines[i];
  const fence=line.match(/^```(\w*)\s*$/);
  if(fence){
   flushPara();flushList();flushQuote();
   const lang=fence[1],code:string[]=[];i++;
   while(i<lines.length&&!/^```\s*$/.test(lines[i])){code.push(lines[i]);i++;}
   i++;
   out.push(`<pre><code${lang?` class="lang-${lang.replace(/[^\w-]/g,'')}"`:''}>${esc(code.join('\n'))}</code></pre>`);
   continue;
  }
  const h=line.match(/^(#{1,3})\s+(.*)$/);
  if(h){flushPara();flushList();flushQuote();out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);i++;continue;}
  const li=line.match(/^[-*]\s+(.*)$/),oli=line.match(/^\d+\.\s+(.*)$/);
  if(li||oli){
   flushPara();flushQuote();
   const tag=li?'ul':'ol';
   if(!list||list.tag!==tag){flushList();list={tag,items:[]};}
   list.items.push((li??oli)![1]);
   i++;continue;
  }
  if(line.includes('|')&&i+1<lines.length&&isSeparatorRow(lines[i+1])){
   flushPara();flushList();flushQuote();
   const header=parseRow(line);i+=2;
   const rows:string[][]=[];
   while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){rows.push(parseRow(lines[i]));i++;}
   const thead=`<thead><tr>${header.map(c=>`<th>${inline(c)}</th>`).join('')}</tr></thead>`;
   const tbody=`<tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody>`;
   out.push(`<div class="table-wrap"><table>${thead}${tbody}</table></div>`);
   continue;
  }
  const bq=line.match(/^>\s?(.*)$/);
  if(bq){flushPara();flushList();quote=quote??[];quote.push(bq[1]);i++;continue;}
  if(!line.trim()){flushPara();flushList();flushQuote();i++;continue;}
  flushList();flushQuote();
  para.push(line);i++;
 }
 flushPara();flushList();flushQuote();
 return out.join('');
}
