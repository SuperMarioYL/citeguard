"""Generate CiteGuard desktop/mobile figures from web/palette.json and demo facts."""
from pathlib import Path
from html import escape
import json,math,re,shutil

ROOT=Path(__file__).resolve().parent.parent
PALETTE=json.loads((ROOT/'web/palette.json').read_text())
RECORD=json.loads((ROOT/'docs/demo-results.json').read_text())
RESULTS=[json.loads(step['output']) for step in RECORD['steps']]


def text(x,y,s,size=24,color='ink',weight=400,anchor='start'):
    assert size>=17
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{P[color]}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(s))}</text>'

def rect(x,y,w,h,fill='panel',stroke='line',r=12):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{P[fill]}" stroke="{P[stroke]}"/>'

def path(d,color='primary',width=2,extra=''):
    return f'<path d="{d}" fill="none" stroke="{P[color]}" stroke-width="{width}" {extra}/>'

def circle(x,y,r,color='primary',extra=''):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{P[color]}" {extra}/>'

def connector(d,color='primary'):
    return path(d,color,1.3,'opacity=".4"')+path(d,color,2.5,'class="flow"')

def lines(x,y,items,size=22,color='ink',gap=30,anchor='start'):
    return ''.join(text(x,y+i*gap,value,size,color,400,anchor) for i,value in enumerate(items))

def write(name,w,h,title,desc,body,mobile=False):
    css='''text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}.flow{stroke-dasharray:6 14;animation:flow 5s linear infinite}.pulse{animation:pulse 4s ease-in-out infinite}.drift{animation:drift 7s ease-in-out infinite}.scan{animation:scan 6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}.slow{animation-delay:-2s}@keyframes flow{to{stroke-dashoffset:-120}}@keyframes pulse{0%,100%{opacity:.45}50%{opacity:1}}@keyframes drift{0%,100%{transform:translate(0,0)}50%{transform:translate(-5px,4px)}}@keyframes scan{0%,100%{opacity:.3}50%{opacity:.9}}@media(prefers-reduced-motion:reduce){.flow,.pulse,.drift,.scan{animation:none!important;transform:none!important}.flow{stroke-dasharray:none}.pulse,.scan{opacity:.75}}'''
    if name == 'scene':
        css += '.flow,.pulse,.drift,.scan{animation:none!important;transform:none!important}.flow{stroke-dasharray:none}'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" data-palette="{PALETTE['id']}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc><defs><radialGradient id="halo"><stop stop-color="{P['primary']}" stop-opacity=".28"/><stop offset="1" stop-color="{P['bg']}" stop-opacity="0"/></radialGradient><linearGradient id="brand"><stop stop-color="{P['primary']}"/><stop offset=".6" stop-color="{P['secondary']}"/><stop offset="1" stop-color="{P['highlight']}"/></linearGradient><pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="{P['line']}" stroke-width=".7" opacity=".55"/></pattern><filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="5"/></filter></defs><style>{css}</style><rect width="{w}" height="{h}" rx="16" fill="{P['bg']}"/><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="15" fill="url(#grid)" stroke="{P['line']}"/>{body}</svg>'''
    path_out=ROOT/'assets'/f'{name}{"-mobile" if mobile else ""}-{theme}.svg'
    path_out.write_text(svg+'\n')
    shutil.copy2(path_out,ROOT/'web/assets'/path_out.name)


def emblem(cx,cy,r):
    b=f'<circle cx="{cx}" cy="{cy}" r="{r*1.8}" fill="url(#halo)"/>'
    # Citation brackets inside a shield express provenance without a false hit verdict.
    d=f'M{cx-r*.72} {cy-r*.72}L{cx} {cy-r}L{cx+r*.72} {cy-r*.72}V{cy+r*.12}Q{cx+r*.62} {cy+r*.68} {cx} {cy+r}Q{cx-r*.62} {cy+r*.68} {cx-r*.72} {cy+r*.12}Z'
    b+=path(d,'primary',8,'opacity=".27" filter="url(#glow)"')
    b+=f'<path d="{d}" fill="{P["panel"]}" stroke="url(#brand)" stroke-width="2"/>'
    b+=path(f'M{cx-r*.17} {cy-r*.35}H{cx-r*.36}V{cy+r*.32}H{cx-r*.17}M{cx+r*.17} {cy-r*.35}H{cx+r*.36}V{cy+r*.32}H{cx+r*.17}','highlight',4)
    b+=circle(cx,cy,4,'secondary','class="pulse"')
    return b


for theme in ['dark','light']:
    P=PALETTE[theme]
    for mobile in [False,True]:
        w=400 if mobile else 920
        # Hero: source lines converge into a citation shield.
        h=500 if mobile else 370
        cx,cy=(200,354) if mobile else (733,180)
        b=emblem(cx,cy,59 if mobile else 73)
        for i in range(7):
            yy=cy-103+i*32
            start=20 if mobile else 548
            b+=connector(f'M{start} {yy}C{cx-100} {yy} {cx-89} {cy} {cx-48} {cy}','secondary' if i%2 else 'primary')
        for i in range(88):
            a=i*2.39996;r=69+(i%11)*6
            x=cx+math.cos(a)*r*(1.14 if mobile else 1.2);y=cy+math.sin(a)*r*.83
            b+=circle(round(x,1),round(y,1),1.2+i%3*.65,['primary','secondary','highlight'][i%3],f'class="{"drift" if i%5==0 else "pulse slow"}" opacity=".65"')
        if not mobile:
            write('scene',w,h,'CiteGuard source-context scene','Illustrative citation shield and particles. No registry result is represented.',b)
        b+=lines(24 if mobile else 48,36 if mobile else 57,['REGISTRY CHECKS','SOURCE CONTEXT'] if mobile else ['REGISTRY CHECKS / SOURCE CONTEXT'],17 if mobile else 19,'muted',25)
        b+=text(20 if mobile else 44,132 if mobile else 169,'CiteGuard',57 if mobile else 89,'ink',700)
        b+=lines(24 if mobile else 48,183 if mobile else 241,['Check references.','Keep the evidence.'],27 if mobile else 32,'primary',38)
        write('hero',w,h,'CiteGuard — check references, keep the evidence','CiteGuard identity. Citation brackets converge into a shield. This is an illustrative brand figure, not a registry lookup result.',b,mobile)

        # Architecture: separate the offline extractor, network checks and outputs.
        if mobile:
            b=lines(24,40,['FOLLOW THE IDENTIFIER'],24,'ink')+text(24,76,'Extraction, lookup, source context',17,'muted')
            b+=rect(24,108,352,85,stroke='primary')+text(200,145,'Document input',25,'ink',600,'middle')+text(200,176,'PDF text · TeX · MD · plain text',18,'muted',400,'middle')
            b+=connector('M200 193V225')
            b+=rect(24,226,352,85,'code','secondary')+text(200,261,'extract.py',25,'ink',600,'middle')+text(200,291,'patterns → normalized identifiers',18,'muted',400,'middle')
            b+=connector('M200 311V343')
            b+=rect(24,344,352,91,stroke='primary')+text(200,380,'Citation',27,'ink',600,'middle')+text(200,412,'kind · identifier · source line',19,'primary',400,'middle')
            b+=text(24,469,'NETWORK REQUIRED BELOW',17,'muted',600)
            b+=rect(24,489,352,219,stroke='secondary')
            b+=lines(44,528,['DOI → OpenAlex','miss → Crossref fallback','arXiv → arXiv API','CVE → NVD','Commit / issue → GitHub'],20,'ink',36)
            b+=connector('M200 708V742','secondary')
            b+=rect(24,743,352,129,stroke='primary')+text(200,777,'VerifyResult → report',24,'ink',600,'middle')+text(200,810,'hit · miss · degraded',21,'primary',400,'middle')+text(200,846,'Evidence URL · JSON · Markdown',18,'muted',400,'middle')
            b+=rect(24,904,352,98,'code','secondary')+text(200,940,'SQLite · 7-day TTL',24,'ink',600,'middle')+text(200,973,'degraded results are not cached',18,'muted',400,'middle')
            b+=text(24,1039,'Cache errors fall back to lookup.',18,'muted')
            h=1070
        else:
            b=text(40,51,'FOLLOW THE IDENTIFIER',32,'ink',600)+text(40,87,'Extraction, registry lookup and source context',22,'muted')
            for x,title,rows,col in [(40,'Document input',['PDF text · TeX','MD · plain text'],'primary'),(342,'extract.py',['Patterns + normalization','No model call'],'secondary'),(644,'Citation',['kind · identifier','file · offsets · line'],'primary')]:
                b+=rect(x,125,236,137,stroke=col)+text(x+18,167,title,25,'ink',600)+lines(x+18,207,rows,19,'muted',28)
            b+=connector('M277 192H341')+connector('M579 192H643')
            b+=text(40,311,'NETWORK REQUIRED FOR VERIFICATION',19,'muted',600)
            b+=rect(40,335,840,168,stroke='secondary')
            b+=lines(65,378,['DOI → OpenAlex','OpenAlex miss → Crossref fallback'],23,'ink',36)
            b+=lines(65,460,['arXiv → arXiv API'],23,'primary')
            b+=lines(527,378,['CVE → NVD','Commit / issue → GitHub'],23,'ink',36)
            b+=connector('M762 263V335','secondary')+connector('M460 504V551')
            b+=rect(40,552,535,126,stroke='primary')+text(62,595,'VerifyResult → report',28,'ink',600)+text(62,632,'hit · miss · degraded',24,'primary')+text(62,660,'Evidence URL · JSON · Markdown',19,'muted')
            b+=rect(606,552,274,126,'code','secondary')+text(626,591,'SQLite · 7-day TTL',24,'ink',600)+lines(626,625,['degraded is not cached','Errors → live lookup'],18,'muted',28)
            b+=connector('M743 503V551','secondary')
            h=710
        write('architecture',w,h,'CiteGuard architecture','Document extraction creates Citation objects with source context. Network verification routes DOI to OpenAlex with Crossref fallback on miss, arXiv to arXiv, CVE to NVD and GitHub references to GitHub. Reports use hit, miss and degraded. The SQLite cache has seven-day TTL and does not persist degraded results.',b,mobile)

        # Offline process: full identifiers and their actual source-line numbers.
        found=RESULTS[0]
        b=lines(24 if mobile else 40,40 if mobile else 51,['EXTRACT. NORMALIZE. LOCATE.'] if not mobile else ['EXTRACT. NORMALIZE.','LOCATE.'],25 if mobile else 31,'ink',33)
        b+=text(24 if mobile else 40,112 if mobile else 90,'Offline demo · no registry lookup',18 if mobile else 22,'muted')
        if mobile:
            b+=rect(24,143,352,163,'code','primary')+text(43,181,'7 lines of source text',25,'ink',600)
            b+=lines(43,219,['Five identifier kinds','Repeated arXiv → one identifier','Context spans retain source lines'],18,'muted',28)
            b+=connector('M200 307V351')+text(24,386,f'{len(found)} unique Citation objects',25,'primary',600)
            yy=413
            for item in found:
                chunks=[item['identifier'][i:i+20] for i in range(0,len(item['identifier']),20)] if item['kind']=='commit' else [item['identifier']]
                hh=78+max(0,len(chunks)-1)*26
                b+=rect(24,yy,352,hh,stroke='secondary')+text(43,yy+29,f"{item['kind']}  ·  line {item['context_span']['line']}",19,'muted',500)
                b+=lines(43,yy+60,chunks,19,'ink',26)
                yy+=hh+14
            b+=text(24,yy+25,'Existence has not been checked.',18,'muted')
            h=yy+55
        else:
            b+=rect(40,136,277,463,'code','primary')+text(61,180,'7 source lines',27,'ink',600)
            b+=lines(61,230,['DOI','arXiv v2','CVE','Anchored commit SHA','GitHub issue URL','Repeated arXiv'],21,'muted',46)
            b+=text(61,563,'Repeat → one identifier',18,'primary')
            b+=connector('M318 365H367')+text(374,167,f'{len(found)} unique Citation objects',27,'primary',600)
            yy=194
            for item in found:
                chunks=[item['identifier'][:20],item['identifier'][20:]] if item['kind']=='commit' else [item['identifier']]
                hh=64+max(0,len(chunks)-1)*22
                b+=rect(372,yy,508,hh,stroke='secondary')
                b+=text(390,yy+25,f"{item['kind']}  ·  line {item['context_span']['line']}",18,'muted',500)
                b+=lines(390,yy+50,chunks,20,'ink',22)
                yy+=hh+11
            b+=text(40,640,'Identifiers were extracted. Their existence has not been checked.',21,'muted')
            h=670
        write('process',w,h,'CiteGuard offline extraction result','The recorded Markdown example has seven lines and yields five unique identifiers: DOI, arXiv, CVE, commit and GitHub issue. The repeated arXiv identifier is deduplicated. Full identifiers and source line numbers are shown; no registry verification occurred.',b,mobile)

        # Integrations: a registry compass, not a dependency-propagation chain.
        if mobile:
            b=lines(24,40,['FIVE KINDS.','REGISTRY-SPECIFIC ROUTES.'],24,'ink',33)+text(24,108,'Implemented lookup and report paths',17,'muted')
            cx,cy=200,489
            nodes=[(200,192,'DOI',['OpenAlex','Crossref fallback'],224),(290,341,'arXiv',['arXiv API'],164),(290,655,'CVE',['NVD'],164),(200,811,'Commit / issue',['GitHub'],224),(110,655,'Documents',['PDF · TeX · MD','plain text'],164),(110,341,'Reports / CI',['JSON · Markdown','GitHub Action'],164)]
            h=954
            b+=f'<ellipse cx="{cx}" cy="{cy}" rx="127" ry="284" fill="none" stroke="{P["line"]}"/>'
        else:
            b=text(40,52,'FIVE KINDS. REGISTRY-SPECIFIC ROUTES.',29,'ink',600)+text(40,90,'Implemented lookup and report paths',21,'muted')
            cx,cy=460,367
            nodes=[(460,167,'DOI',['OpenAlex → Crossref fallback'],310),(744,254,'arXiv',['arXiv API'],236),(744,476,'CVE',['NVD'],236),(460,569,'Commit / issue',['GitHub'],310),(176,476,'Documents',['PDF · TeX · MD','plain text'],236),(176,254,'Reports / CI',['JSON · Markdown','GitHub Action'],236)]
            h=676
            b+=f'<ellipse cx="{cx}" cy="{cy}" rx="286" ry="195" fill="none" stroke="{P["line"]}"/>'
        b+=emblem(cx,cy,56 if mobile else 65)
        for i,(x,y,title,labels,nw) in enumerate(nodes):
            d=math.hypot(x-cx,y-cy);sx=cx+(x-cx)/d*71;sy=cy+(y-cy)/d*71
            b+=connector(f'M{sx:.1f} {sy:.1f}L{x} {y}','secondary' if i%2 else 'primary')
            nh=102 if len(labels)>1 else 83
            b+=rect(x-nw/2,y-nh/2,nw,nh,stroke='secondary' if i%2 else 'primary')
            b+=text(x,y-nh/2+32,title,21 if mobile else 25,'ink',600,'middle')
            b+=lines(x,y-nh/2+61,labels,17 if mobile else 18,'muted',24,'middle')
        b+=text(24 if mobile else 40,h-46,'Verification requires network access.',18 if mobile else 21,'muted')
        write('integrations',w,h,'CiteGuard integrations','DOI lookups use OpenAlex and Crossref fallback, arXiv uses arXiv, CVE uses NVD, and commits or issues use GitHub. Documents are text-layer PDF, TeX, Markdown or plain text. Outputs include JSON, Markdown and a GitHub Action. These are implemented routes, not live connection status.',b,mobile)

    # Extra recorded snapshots avoid showing the first input's count on later demo steps.
    for index,name in [(1,'demo-normalized'),(2,'demo-boundaries')]:
        found=RESULTS[index]
        b=text(40,52,'OFFLINE EXTRACTION',29,'ink',600)+text(40,91,RECORD['steps'][index]['command'].split()[1],22,'muted')
        for i,item in enumerate(found):
            y=136+i*119
            b+=rect(40,y,840,98,stroke='primary' if i==0 else 'secondary')
            b+=text(62,y+35,f"{item['kind']}  ·  line {item['context_span']['line']}",21,'muted')+text(62,y+75,item['identifier'],27,'ink',500)
        foot='Case and arXiv versions normalize; duplicate identifiers collapse.' if index==1 else 'A DOI fragment stays DOI; the unanchored hash is not extracted.'
        b+=text(40,416,foot,21,'muted')+text(40,456,'No registry lookup. No existence verdict.',21,'primary')
        write(name,920,490,'CiteGuard recorded extraction snapshot',foot+' This image uses the exact identifiers from the corresponding CLI output.',b)
print('Generated palette-bound desktop/mobile SVGs and byte-identical web copies:',PALETTE['id'])
