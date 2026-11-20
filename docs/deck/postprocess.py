"""Add slide transitions and entrance animations to the pptxgenjs output.

- Every slide gets a fade transition; slides whose pictures are named "!!..." (shared with
  the previous slide) get a Morph transition with a fade fallback, giving a smooth zoom.
- Shapes named anim_NN[_part] fade in automatically after the slide appears, grouped by NN
  and staggered, so each row/column builds in order without clicks.
Usage: python postprocess.py Upsolve.pptx
"""

import re
import shutil
import sys
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

from lxml import etree

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
P = "{%s}" % NS["p"]
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
P159 = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"

STAGGER_MS = 350   # gap between groups
FADE_MS = 500
FIRST_DELAY_MS = 300


def transition_xml(morph: bool) -> etree._Element:
    if not morph:
        return etree.fromstring(f'<p:transition xmlns:p="{NS["p"]}" spd="med"><p:fade/></p:transition>')
    return etree.fromstring(
        f'<mc:AlternateContent xmlns:mc="{MC}" xmlns:p="{NS["p"]}">'
        f'<mc:Choice xmlns:p159="{P159}" xmlns:p14="{P14}" Requires="p159">'
        f'<p:transition spd="slow" p14:dur="1400"><p159:morph option="byObject"/></p:transition>'
        f'</mc:Choice><mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback>'
        f'</mc:AlternateContent>')


def timing_xml(groups: "OrderedDict[str, list[tuple[str, bool]]]") -> etree._Element:
    ids = iter(range(3, 10_000))
    effects, builds = [], []
    for gi, (_, members) in enumerate(groups.items()):
        delay = FIRST_DELAY_MS + gi * STAGGER_MS
        for mi, (spid, is_text) in enumerate(members):
            node = "afterEffect" if (gi == 0 and mi == 0) else "withEffect"
            c1, c2, c3 = next(ids), next(ids), next(ids)
            grp = ' grpId="0"' if is_text else ""
            effects.append(
                f'<p:par><p:cTn id="{c1}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold"{grp} nodeType="{node}">'
                f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{c2}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
                f'<p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{c3}" dur="{FADE_MS}"/>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
                f'</p:childTnLst></p:cTn></p:par>')
            if is_text:
                builds.append(f'<p:bldP spid="{spid}" grpId="0"/>')
    bld = f'<p:bldLst>{"".join(builds)}</p:bldLst>' if builds else ""
    xml = (
        f'<p:timing xmlns:p="{NS["p"]}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        f'<p:par><p:cTn id="9001" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
        f'<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
        f'<p:par><p:cTn id="9002" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        f'{"".join(effects)}'
        f'</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>'
        f'</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
        f'</p:childTnLst></p:cTn></p:par></p:tnLst>{bld}</p:timing>')
    return etree.fromstring(xml)


def process(path: Path):
    tmp = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(path) as z:
        z.extractall(tmp)
        names = z.namelist()
    slides = sorted((tmp / "ppt/slides").glob("slide*.xml"), key=lambda p: int(re.findall(r"\d+", p.name)[0]))
    prev_morph_names: set[str] = set()
    for sp in slides:
        tree = etree.parse(str(sp))
        root = tree.getroot()
        shapes = root.findall(".//p:cSld/p:spTree/*", NS)
        groups: "OrderedDict[str, list]" = OrderedDict()
        morph_names = set()
        for el in shapes:
            nv = el.find(".//p:cNvPr", NS)
            if nv is None:
                continue
            name = nv.get("name", "")
            if name.startswith("!!"):
                morph_names.add(name)
            m = re.match(r"anim_(\d+)", name)
            if m:
                groups.setdefault(m.group(1), []).append((nv.get("id"), el.tag == P + "sp" and el.find("p:txBody", NS) is not None))
        groups = OrderedDict(sorted(groups.items(), key=lambda kv: int(kv[0])))
        for old in root.findall("p:transition", NS) + root.findall("p:timing", NS):
            root.remove(old)
        clr = root.find("p:clrMapOvr", NS)
        idx = list(root).index(clr) + 1 if clr is not None else list(root).index(root.find("p:cSld", NS)) + 1
        morph = bool(morph_names & prev_morph_names)
        root.insert(idx, transition_xml(morph))
        if groups:
            root.insert(idx + 1, timing_xml(groups))
        tree.write(str(sp), xml_declaration=True, encoding="UTF-8", standalone=True)
        prev_morph_names = morph_names
        print(f"{sp.name}: {'morph' if morph else 'fade'}, {len(groups)} animated groups")
    out = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:  # keep the original part order ([Content_Types].xml first)
            z.write(tmp / n, n)
    shutil.move(out, path)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    process(Path(sys.argv[1]))
