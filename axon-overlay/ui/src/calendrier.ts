//: Calculs de dates du composant Calendrier — purs, pour être testés seuls.

//: « 2026-10-12 » en heure LOCALE. `toISOString()` passe en UTC et décale
//: d'un jour près de minuit : jamais utilisé ici.
export function isoLocal(d:Date):string{
 const mois=String(d.getMonth()+1).padStart(2,'0');
 const jour=String(d.getDate()).padStart(2,'0');
 return `${d.getFullYear()}-${mois}-${jour}`;
}

export interface CaseJour { iso:string; jour:number; dansLeMois:boolean }

//: Les 42 cases (6 semaines, lundi en premier) qui affichent le mois
//: `mois` (0-11) de `annee`, avec les jours voisins pour compléter.
export function casesDuMois(annee:number,mois:number):CaseJour[]{
 const premier=new Date(annee,mois,1);
 const decalage=(premier.getDay()+6)%7;
 const cases:CaseJour[]=[];
 for(let i=0;i<42;i++){
  const d=new Date(annee,mois,1-decalage+i);
  cases.push({iso:isoLocal(d),jour:d.getDate(),dansLeMois:d.getMonth()===mois});
 }
 return cases;
}
