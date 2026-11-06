#!/usr/bin/env python3
"""Build a Windhawk named-symbol cache file for Helium Acrylic.

Usage: make_cache.py chrome.dll chrome.dll.pdb out_dir
Writes out_dir/pdb_<GUID><age>.txt and prints a JSON summary.

Format (Windhawk online symbol cache, same as bardelyne's Brave Acrylic):
  1#chrome.dll#x86-64_<TimeDateStamp>_<SizeOfImage>#<name>#<decimal RVA>#...
An empty RVA marks an optional symbol that is absent from this build.
The order and names must match the SYMBOL_HOOK array in helium-acrylic.wh.cpp.
"""
import json, mmap, os, struct, sys, uuid

# (Windhawk undecorated name, exact decorated PDB public name, required)
SLOTS = [
    ("protected: virtual void __cdecl views::View::OnPaintBackground(class gfx::Canvas *)",
     "?OnPaintBackground@View@views@@MEAAXPEAVCanvas@gfx@@@Z", True),
    ("public: void __cdecl gfx::Canvas::DrawColor(unsigned int,enum SkBlendMode)",
     "?DrawColor@Canvas@gfx@@QEAAXIW4SkBlendMode@@@Z", True),
    ("public: class std::__Cr::basic_string_view<char,struct std::__Cr::char_traits<char> > __cdecl views::View::GetClassNameW(void)const",
     "?GetClassNameW@View@views@@QEBA?AV?$basic_string_view@DU?$char_traits@D@__Cr@std@@@__Cr@std@@XZ", True),
    ("private: virtual bool __cdecl BrowserDesktopWindowTreeHostWin::ShouldWindowContentsBeTransparent(void)const",
     "?ShouldWindowContentsBeTransparent@BrowserDesktopWindowTreeHostWin@@EEBA_NXZ", True),
    ("public: __cdecl BraveVerticalTabStripContainerView::BraveVerticalTabStripContainerView(class BrowserView *,class views::View *)",
     "??0BraveVerticalTabStripContainerView@@QEAA@PEAVBrowserView@@PEAVView@views@@@Z", False),  # Brave only
    ("public: void __cdecl views::View::SetBackground(class std::__Cr::unique_ptr<class views::Background,struct std::__Cr::default_delete<class views::Background> >)",
     "?SetBackground@View@views@@QEAAXV?$unique_ptr@VBackground@views@@U?$default_delete@VBackground@views@@@__Cr@std@@@__Cr@std@@@Z", True),
    ("public: virtual bool __cdecl LocationBarView::HasFocus(void)const",
     "?HasFocus@LocationBarView@@UEBA_NXZ", True),
    ("public: virtual bool __cdecl views::View::HasFocus(void)const",
     "?HasFocus@View@views@@UEBA_NXZ", True),
    ("public: virtual void __cdecl ContentsWebView::OnThemeChanged(void)",
     "?OnThemeChanged@ContentsWebView@@UEAAXXZ", True),
    ("public: virtual void __cdecl ContentsWebView::RenderViewReady(void)",
     "?RenderViewReady@ContentsWebView@@UEAAXXZ", True),
    ("public: virtual void __cdecl ui::LayerAnimator::SetColor(struct SkRGBA4f<3>)",
     "?SetColor@LayerAnimator@ui@@UEAAXU?$SkRGBA4f@$02@@@Z", True),
    ("public: virtual void __cdecl content::WebContentsImpl::SetPageBaseBackgroundColor(class std::__Cr::optional<unsigned int>)",
     "?SetPageBaseBackgroundColor@WebContentsImpl@content@@UEAAXV?$optional@I@__Cr@std@@@Z", True),
    ("public: virtual void __cdecl ContentsWebView::SetWebContents(class content::WebContents *)",
     "?SetWebContents@ContentsWebView@@UEAAXPEAVWebContents@content@@@Z", True),
    ("struct HWND__ * __cdecl views::HWNDForView(class views::View const *)",
     "?HWNDForView@views@@YAPEAUHWND__@@PEBVView@1@@Z", True),
    ("public: unsigned int __cdecl ui::ColorProvider::GetColor(int)const",
     "?GetColor@ColorProvider@ui@@QEBAIH@Z", True),
    ("public: virtual void __cdecl views::MenuScrollViewContainer::OnPaintBackground(class gfx::Canvas *)",
     "?OnPaintBackground@MenuScrollViewContainer@views@@UEAAXPEAVCanvas@gfx@@@Z", True),
    ("public: virtual void __cdecl views::BubbleBackground::Paint(class gfx::Canvas *,class views::View *)const",
     "?Paint@BubbleBackground@views@@UEBAXPEAVCanvas@gfx@@PEAVView@2@@Z", True),
    ("public: virtual void __cdecl cc::RecordPaintCanvas::drawRRect(class SkRRect const &,class cc::PaintFlags const &)",
     "?drawRRect@RecordPaintCanvas@cc@@UEAAXAEBVSkRRect@@AEBVPaintFlags@2@@Z", True),
    ("public: __cdecl RoundedOmniboxResultsFrame::RoundedOmniboxResultsFrame(class views::View *,class LocationBar *,bool)",
     "??0RoundedOmniboxResultsFrame@@QEAA@PEAVView@views@@PEAVLocationBar@@_N@Z", True),
    ("public: virtual __cdecl RoundedOmniboxResultsFrame::~RoundedOmniboxResultsFrame(void)",
     "??1RoundedOmniboxResultsFrame@@UEAA@XZ", True),
    ("private: virtual void __cdecl ui::Layer::SetRoundedCornersFromAnimation(class gfx::RoundedCornersF const &,enum ui::PropertyChangeReason)",
     "?SetRoundedCornersFromAnimation@Layer@ui@@EEAAXAEBVRoundedCornersF@gfx@@W4PropertyChangeReason@2@@Z", True),
    ("public: virtual void __cdecl views::SolidBackground::Paint(class gfx::Canvas *,class views::View *)const",
     "?Paint@SolidBackground@views@@UEBAXPEAVCanvas@gfx@@PEAVView@2@@Z", True),
    ("public: class gfx::Rect __cdecl views::View::GetLocalBounds(void)const",
     "?GetLocalBounds@View@views@@QEBA?AVRect@gfx@@XZ", True),
    ("public: static int __cdecl RoundedOmniboxResultsFrame::GetNonResultSectionHeight(bool)",
     "?GetNonResultSectionHeight@RoundedOmniboxResultsFrame@@SAH_N@Z", True),
    ("const views::SolidBackground::`vftable'",
     "??_7SolidBackground@views@@6B@", True),
    ("public: virtual void __cdecl views::BubbleFrameView::OnThemeChanged(void)",
     "?OnThemeChanged@BubbleFrameView@views@@UEAAXXZ", True),
    ("public: void __cdecl ui::Layer::SetFillsBoundsOpaquely(bool)",
     "?SetFillsBoundsOpaquely@Layer@ui@@QEAAX_N@Z", True),
    ("public: virtual void __cdecl FadeLabel::OnPaintBackground(class gfx::Canvas *)",
     "?OnPaintBackground@FadeLabel@@UEAAXPEAVCanvas@gfx@@@Z", True),
    ("public: class gfx::Rect __cdecl views::View::GetBoundsInScreen(void)const",
     "?GetBoundsInScreen@View@views@@QEBA?AVRect@gfx@@XZ", True),
    ("public: static void __cdecl RoundedOmniboxResultsFrame::OnBeforeWidgetInit(struct views::Widget::InitParams *,class views::Widget *)",
     "?OnBeforeWidgetInit@RoundedOmniboxResultsFrame@@SAXPEAUInitParams@Widget@views@@PEAV34@@Z", True),
    # Helium-only: rounded web-contents frame
    ("public: virtual void __cdecl MultiContentsBackgroundView::OnThemeChanged(void)",
     "?OnThemeChanged@MultiContentsBackgroundView@@UEAAXXZ", False),
    ("public: void __cdecl ui::LayerSolidColor::SetColor(struct SkRGBA4f<3>)",
     "?SetColor@LayerSolidColor@ui@@QEAAXU?$SkRGBA4f@$02@@@Z", False),
    ("private: virtual void __cdecl ContentsContainerOutline::OnPaint(class gfx::Canvas *)",
     "?OnPaint@ContentsContainerOutline@@EEAAXPEAVCanvas@gfx@@@Z", False),
]


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def read_pe(path):
    with open(path, "rb") as f:
        d = f.read(0x2000)
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        if d[pe:pe + 4] != b"PE\0\0":
            fail("chrome.dll is not a PE file")
        machine, nsec, timestamp = struct.unpack_from("<HHI", d, pe + 4)
        if machine != 0x8664:
            fail("chrome.dll is not x64")
        opt_size = struct.unpack_from("<H", d, pe + 20)[0]
        opt = pe + 24
        size_of_image = struct.unpack_from("<I", d, opt + 56)[0]
        dbg_rva, dbg_size = struct.unpack_from("<II", d, opt + 112 + 6 * 8)
        secs = []
        for i in range(nsec):
            vsize, va, rsize, raw = struct.unpack_from("<IIII", d, opt + opt_size + i * 40 + 8)
            secs.append((va, vsize, rsize, raw))

        def off(rva):
            for va, vs, rs, raw in secs:
                if va <= rva < va + max(vs, rs):
                    return rva - va + raw
            fail("RVA not mapped")

        guid = age = None
        for e in range(dbg_size // 28):
            f.seek(off(dbg_rva) + e * 28)
            ent = f.read(28)
            typ, _, rva_data, ptr = struct.unpack_from("<IIII", ent, 12)
            if typ != 2:
                continue
            f.seek(ptr)
            cv = f.read(24)
            if cv[:4] == b"RSDS":
                guid = uuid.UUID(bytes_le=cv[4:20])
                age = struct.unpack_from("<I", cv, 20)[0]
        if guid is None:
            fail("no RSDS record in chrome.dll")
    return dict(timestamp=timestamp, size=size_of_image, secs=[s[0] for s in secs],
                guid=guid, age=age)


class Pdb:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        if not self.m[:32].startswith(b"Microsoft C/C++ MSF 7.00"):
            fail("chrome.dll.pdb is not an MSF 7 PDB")
        self.bs, _, _, dir_bytes, _, map_addr = struct.unpack_from("<IIIIII", self.m, 32)
        n = (dir_bytes + self.bs - 1) // self.bs
        dir_blocks = struct.unpack_from("<%dI" % n, self.m, map_addr * self.bs)
        d = b"".join(self.m[b * self.bs:(b + 1) * self.bs] for b in dir_blocks)[:dir_bytes]
        ns = struct.unpack_from("<I", d, 0)[0]
        sizes = list(struct.unpack_from("<%dI" % ns, d, 4))
        p = 4 + 4 * ns
        self.streams = []
        for sz in sizes:
            sz = 0 if sz == 0xFFFFFFFF else sz
            nb = (sz + self.bs - 1) // self.bs
            self.streams.append((sz, struct.unpack_from("<%dI" % nb, d, p)))
            p += 4 * nb

    def stream(self, i):
        sz, blocks = self.streams[i]
        return b"".join(self.m[b * self.bs:(b + 1) * self.bs] for b in blocks)[:sz]


def main():
    dll, pdb_path, out_dir = sys.argv[1:4]
    pe = read_pe(dll)
    pdb = Pdb(pdb_path)
    info = pdb.stream(1)
    pdb_guid = uuid.UUID(bytes_le=info[12:28])
    if pdb_guid != pe["guid"]:
        fail("PDB GUID %s does not match chrome.dll %s" % (pdb_guid, pe["guid"]))
    dbi = pdb.stream(3)
    dbi_age = struct.unpack_from("<I", dbi, 8)[0]
    if dbi_age != pe["age"]:
        fail("PDB DBI age %d does not match chrome.dll age %d" % (dbi_age, pe["age"]))
    sym = pdb.stream(struct.unpack_from("<H", dbi, 20)[0])

    results = []
    for undecorated, decorated, required in SLOTS:
        needle = decorated.encode("ascii") + b"\0"
        rva = None
        start = 0
        while True:
            i = sym.find(needle, start)
            if i < 0:
                break
            start = i + 1
            h = i - 14  # S_PUB32: len(2) kind(2) flags(4) offset(4) seg(2) name
            if h < 0:
                continue
            _len, kind, _flags, offset, seg = struct.unpack_from("<HHIIH", sym, h)
            if kind != 0x110E:
                continue
            if 1 <= seg <= len(pe["secs"]):
                rva = pe["secs"][seg - 1] + offset
                break
        if rva is not None and not (0 < rva < pe["size"]):
            fail("RVA out of range for " + decorated)
        results.append((undecorated, decorated, required, rva))

    missing_required = [d for _, d, r, v in results if r and v is None]
    fields = ["1", "chrome.dll", "x86-64_%d_%d" % (pe["timestamp"], pe["size"])]
    for undecorated, _, _, rva in results:
        fields += [undecorated, "" if rva is None else str(rva)]
    text = "#".join(fields)
    if "#" in "".join(u for u, *_ in results):
        fail("symbol name contains '#'")
    if len(missing_required) > 10:
        fail("too many required symbols missing (%d); refusing to publish" % len(missing_required))
    key = pe["guid"].hex.upper() + "%X" % pe["age"]
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "pdb_%s.txt" % key)
    with open(out, "w", encoding="ascii", newline="") as f:
        f.write(text)
    summary = dict(key=key, timestamp=pe["timestamp"], sizeOfImage=pe["size"], file=out,
                   missingRequired=missing_required,
                   symbols=[dict(name=d, rva=None if v is None else "0x%X" % v)
                            for _, d, _, v in results])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
