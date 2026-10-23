"""Build the local test app "3D-PrintDash TEST" from the printdash/ folder.

The test app has exactly the same features. Only the outside differs, so it can be
installed next to the normal version without being mixed up:
  - name "3D-PrintDash TEST", slug printdash_test, version "<x.y.z>-test"
  - own sidebar entry (title "PrintDash TEST", test tube icon)
  - orange "TEST VERSION" bar in the interface (PRINTDASH_TEST=1)
  - built on the Home Assistant machine itself (no image: line)
  - orange "TEST" badge on icon and logo (needs Pillow, skipped otherwise)

Usage:  python3 make_test_app.py <path/to/printdash> <output folder>
The result is <output folder>/printdash – copy it into the addons/ share of Home Assistant.
"""
import os
import re
import shutil
import sys


def badge(path, text="TEST"):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    d = ImageDraw.Draw(im)
    band = max(14, h // 4)
    d.rectangle([0, h - band, w, h], fill=(249, 115, 22, 255))
    font = None
    for f in ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, int(band * 0.7))
            break
    font = font or ImageFont.load_default()
    tw = d.textlength(text, font=font)
    d.text(((w - tw) / 2, h - band + band * 0.1), text, font=font, fill=(28, 13, 2, 255))
    im.save(path, optimize=True)


def main(src, out_root):
    dst = os.path.join(out_root, "printdash")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    cfg_path = os.path.join(dst, "config.yaml")
    cfg = open(cfg_path, encoding="utf-8").read()
    cfg = re.sub(r"^# prebuilt images.*\n(#.*\n)*", "", cfg, flags=re.M)
    cfg = re.sub(r"^image:.*\n", "", cfg, flags=re.M)
    cfg = re.sub(r"^name:.*$", "name: 3D-PrintDash TEST", cfg, flags=re.M)
    cfg = re.sub(r"^slug:.*$", "slug: printdash_test", cfg, flags=re.M)
    cfg = re.sub(r'^version:\s*"?([^"\n]+)"?', lambda m: f'version: "{m.group(1)}-test"', cfg, flags=re.M)
    cfg = re.sub(r"^description:\s*", "description: TEST VERSION – ", cfg, flags=re.M)
    cfg = re.sub(r"^panel_title:.*$", "panel_title: PrintDash TEST", cfg, flags=re.M)
    cfg = re.sub(r"^panel_icon:.*$", "panel_icon: mdi:test-tube", cfg, flags=re.M)
    assert "image:" not in cfg and "slug: printdash_test" in cfg
    open(cfg_path, "w", encoding="utf-8").write(cfg)

    docker_path = os.path.join(dst, "Dockerfile")
    docker = open(docker_path, encoding="utf-8").read()
    docker = docker.replace("ENV PRINTDASH_DATA=/data \\", "ENV PRINTDASH_DATA=/data \\\n    PRINTDASH_TEST=1 \\", 1)
    assert "PRINTDASH_TEST=1" in docker
    open(docker_path, "w", encoding="utf-8").write(docker)

    note = ("> **Test version.** Same features as 3D-PrintDash, for trying out updates before they are "
            "published. Stop the normal version while testing.\n>\n> **Testversion.** Gleiche Funktionen wie "
            "3D-PrintDash, zum Ausprobieren von Updates vor der Veröffentlichung. Die normale Version "
            "währenddessen stoppen.\n\n")
    for name in ("README.md", "DOCS.md"):
        p = os.path.join(dst, name)
        if os.path.exists(p):
            text = open(p, encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(note + text)

    for name in ("icon.png", "logo.png"):
        p = os.path.join(dst, name)
        if os.path.exists(p):
            badge(p)
    print("Test app built:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
