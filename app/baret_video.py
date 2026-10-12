"""Command line alternative: python -m app.baret_video --kind video --source film.mp4"""
import argparse
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent.parent / '.yolo'))
Path(os.environ['YOLO_CONFIG_DIR']).mkdir(parents=True, exist_ok=True)
from .engine import ROOT, process

def main():
    parser = argparse.ArgumentParser(description='Baret tespiti ve sonuç kaydı')
    parser.add_argument('--kind', choices=['image', 'video', 'camera'], default='video')
    parser.add_argument('--source', required=True)
    parser.add_argument('--model', default=str(ROOT / 'models' / 'best.pt'))
    parser.add_argument('--output', default=str(ROOT / 'results'))
    parser.add_argument('--confidence', type=float, default=.5)
    args = parser.parse_args()
    print(process(args.source, args.kind, args.model, args.output, args.confidence))

if __name__ == '__main__':
    main()
