"""Build project-local review artifacts with the installed ppt-master compiler."""
from pathlib import Path
import argparse,json,subprocess,sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-dir',type=Path,default=Path.home()/'.codex/skills/ppt-master')
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(args.skill_dir/'scripts'))
    from attribution_guard import require_skill_integrity
    from slide_roster import discover_slide_svgs
    from template_preview_pptx import _review_svg_sources,_verify_output
    from svg_to_pptx.pptx_package.builder import create_pptx_with_native_svg
    from svg_to_pptx.drawingml.theme_fonts import load_theme_font_spec,load_master_text_style_spec
    from svg_to_pptx.drawingml.theme_colors import load_theme_color_spec
    require_skill_integrity()
    checker=args.skill_dir/'scripts/svg_quality_checker.py'
    reports={}
    for folder,extra in [('templates',['--template-mode']),('svg_output',[])]:
        command=[sys.executable,str(checker),str(root/folder),'--canonical-authoring','--format','ppt169',*extra]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (root/'validation'/f'{folder}-quality.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode: raise RuntimeError(f'{folder} quality gate failed; see validation/{folder}-quality.txt')
        reports[folder]={'exit_code':result.returncode,'pages':len(discover_slide_svgs(root/folder))}
    for folder,filename,shorten in [('templates','academic-formal_template_preview.pptx',True),('svg_output','academic-formal_sample.pptx',False)]:
        target=root/'exports'/filename
        if target.exists() and not args.force: raise FileExistsError(f'{target}; use --force for intentional replacement')
        with _review_svg_sources(root,discover_slide_svgs(root/folder),shorten_placeholder_markers=shorten) as svgs:
            success=create_pptx_with_native_svg(svg_files=svgs,output_path=target,resource_root=root,canvas_format=None,expected_viewbox='0 0 1280 720',verbose=False,transition=None,enable_notes=False,animation=None,image_optimize=False,native_objects=False,pptx_structure='structured',use_layout_placeholder_frames=True,master_text_style_spec=load_master_text_style_spec(root),theme_font_spec=load_theme_font_spec(root,language='zh-CN'),theme_color_spec=load_theme_color_spec(root),structure_name='academic-formal')
        if not success: raise RuntimeError('PPTX compilation failed')
        slides,masters,layouts,slots=_verify_output(target,require_full_placeholder_frames=True)
        reports[filename]={'slides':slides,'masters':masters,'layouts':layouts,'full_frame_placeholders':slots,'bytes':target.stat().st_size}
    (root/'validation/build-report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(reports,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
