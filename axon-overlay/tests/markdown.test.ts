import {describe,it,expect} from 'vitest';
import {renderMarkdown} from '../ui/src/markdown';
describe('rendu markdown minimal',()=>{
 it('échappe le HTML brut avant toute transformation',()=>{expect(renderMarkdown('<img src=x onerror=attack()>')).not.toContain('<img');expect(renderMarkdown('<img src=x onerror=attack()>')).toContain('&lt;img');});
 it('rend gras, italique, code et lien en ligne',()=>{expect(renderMarkdown('**gras** *italique* `code` [lien](https://ex.com)')).toBe('<p><strong>gras</strong> <em>italique</em> <code>code</code> <a href="https://ex.com" target="_blank" rel="noopener noreferrer">lien</a></p>');});
 it('rend un bloc de code sans interpréter son contenu',()=>{expect(renderMarkdown('```ts\nconst a = 1;\n```')).toBe('<pre><code class="lang-ts">const a = 1;</code></pre>');});
 it('regroupe une liste à puces et une liste numérotée séparément',()=>{expect(renderMarkdown('- a\n- b\n\n1. x\n2. y')).toBe('<ul><li>a</li><li>b</li></ul><ol><li>x</li><li>y</li></ol>');});
 it('rend titres et citations',()=>{expect(renderMarkdown('## Titre\n> une citation')).toBe('<h2>Titre</h2><blockquote>une citation</blockquote>');});
 it('sépare deux paragraphes et garde les retours à la ligne simples',()=>{expect(renderMarkdown('ligne 1\nligne 2\n\nautre paragraphe')).toBe('<p>ligne 1<br>ligne 2</p><p>autre paragraphe</p>');});
 it('rend un tableau GFM complet, sans tronquer les lignes',()=>{
  const table=
   '| # | Expéditeur | Objet |\n'+
   '|---|------------|-------|\n'+
   '| 1 | Laura | Re: Entretien |\n'+
   '| 2 | Hugo | Build cassé |\n'+
   '| 3 | Camille | Point hebdo |';
  const rendu=renderMarkdown(table);
  expect(rendu).toContain('<thead><tr><th>#</th><th>Expéditeur</th><th>Objet</th></tr></thead>');
  expect(rendu).toContain('<td>Laura</td>');
  expect(rendu).toContain('<td>Hugo</td>');
  expect(rendu).toContain('<td>Camille</td>'); // les 3 lignes, pas juste la première
 });
 it('un texte avec des barres verticales mais sans ligne de séparation reste un paragraphe',()=>{
  expect(renderMarkdown('a | b | c')).toBe('<p>a | b | c</p>');
 });
});
