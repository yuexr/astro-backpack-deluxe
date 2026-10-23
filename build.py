"""Build commands for Backpack Deluxe. Run `python build.py --help` for configuration."""
import argparse,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))

def main():
    parser=argparse.ArgumentParser(description='Backpack Deluxe 0.1.11 source tools (Windows / Astroneer 1.45.1.0).',
        epilog='Install requirements.txt. Set BPD_REPAK, BPD_UASSETGUI and BPD_UMODEL to external executables, or put them in tools/. Set BPD_GAME_PAK if Astroneer is installed elsewhere. The approved mesh export is models/backpack-deluxe.glb. The Blender file is an optional inspection copy, and Blender is not required to build. Generated assets and dist/ are ignored. Nothing is installed into the game.')
    parser.add_argument('command',choices=['prepare','build','verify','package'])
    args=parser.parse_args()
    from investigate import PAK,REPAK,GUI,UMODEL
    if args.command in ['prepare','build','verify']:
        for label,path in [('BPD_GAME_PAK',PAK),('BPD_REPAK',REPAK),('BPD_UASSETGUI',GUI),('BPD_UMODEL',UMODEL)]:
            if not path.is_file():parser.error(f'{label} does not point to an existing file: {path}')
    def run(script):subprocess.run([sys.executable,str(ROOT/'scripts'/script)],check=True)
    if args.command=='prepare':run('prepare_assets.py')
    elif args.command=='build':
        run('prepare_assets.py');run('build_game_prototype_0111.py');run('verify_game_prototype_0111.py')
    elif args.command=='verify':run('verify_game_prototype_0111.py')
    elif args.command=='package':
        run('verify_game_prototype_0111.py');run('package_revision_0111.py')

if __name__=='__main__':main()
