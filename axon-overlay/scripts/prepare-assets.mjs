import {readdir,readFile,mkdir,writeFile} from 'node:fs/promises';
const directory=new URL('../ui/mascots/',import.meta.url);
await mkdir(new URL('static/',directory),{recursive:true});
for(const name of await readdir(directory)){
 if(!name.endsWith('.svg'))continue;
 const source=await readFile(new URL(name,directory),'utf8');
 await writeFile(new URL('static/'+name,directory),source.replace('</style>','*{animation:none!important;transition:none!important}</style>'));
}
