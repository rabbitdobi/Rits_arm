"""Render a synthetic demonstration or replay saved D455 captures, without USB."""
import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path
from types import SimpleNamespace as Point

import cv2
import numpy as np
from unified_control import UnifiedController, palm_frame
from unified_view import draw_unified_panel
from recording import VideoRecorder


def synthetic_hand(closed=0., twist=0.):
    p = np.zeros((21, 3))
    for ids, x, y in (((5,6,7,8),-.04,.05), ((9,10,11,12),0,.06),
                       ((13,14,15,16),.02,.055), ((17,18,19,20),.04,.05)):
        for j, i in enumerate(ids):
            p[i] = [x, y+j*.02, 0]
    for j,i in enumerate((1,2,3,4)):
        p[i] = [-.03-j*.02, .01+j*.01, 0]
    for i,x in ((4,.02),(8,-.02),(12,0),(16,.01),(20,.02)):
        p[i] = (1-closed)*p[i] + closed*np.array([x,.04,0])
    points = [Point(x=x,y=y,z=z) for x,y,z in p]
    axis = palm_frame(points)[:,1]
    cross = np.array([[0,-axis[2],axis[1]], [axis[2],0,-axis[0]], [-axis[1],axis[0],0]])
    rotation = np.eye(3)*math.cos(twist)+(1-math.cos(twist))*np.outer(axis,axis)+math.sin(twist)*cross
    return [Point(x=x,y=y,z=z) for x,y,z in p @ rotation.T]


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    controller = UnifiedController()
    counts = {k:0 for k in ('frames','fingers_valid','wrist_valid','arm_valid')}
    with ExitStack() as stack:
        log = stack.enter_context((args.output/'targets.jsonl').open('x'))
        video = VideoRecorder(args.output/'preview.mp4', 30 if args.samples is None else 1, (1220,480))
        stack.callback(video.close)
        detector = None
        files = sorted(args.samples.glob('*.json')) if args.samples else range(240)
        if args.samples:
            if not files:
                raise ValueError('No diagnostic samples found')
            import mediapipe as mp
            from motion import select_right_hand
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(Path(__file__).parent.parent/'models/hand_landmarker.task')),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2)
            detector = stack.enter_context(mp.tasks.vision.HandLandmarker.create_from_options(options))
        for i,item in enumerate(files):
            if args.samples:
                saved = json.loads(item.read_text())
                with np.load(item.with_suffix('.npz')) as arrays:
                    image = arrays['color_bgr'].copy()
                t = saved['timestamp_ms']
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)), int(t))
                index = select_right_hand(result, prefer_largest=True)
                points = None if index is None else result.hand_world_landmarks[index]
                measured = saved['depth']
                # Replay displays recorded metric measurements; no fresh depth or inferred calibration.
                banner = 'RECORDED: 1 sample/sec playback; uncalibrated'
            else:
                t = i*1000/30
                phase = max(0,(i-35)/30)
                closed = 0 if i<12 else 1 if i<24 else (1-math.cos(phase*2))/2
                points = synthetic_hand(closed, 0 if i<35 else .5*math.sin(phase))
                xyz = [.1,.2,.6] if i<35 else [.1+.04*math.sin(phase), .2-.03*math.sin(phase*.8), .6-.05*math.sin(phase*.7)]
                measured = {'points': {'Palm':dict(valid=True, **dict(zip(('X_m','Y_m','Z_m'),xyz)))}}
                image = np.full((480,640,3),28,np.uint8)
                pix = [(int(320+p.x*1700), int(370-p.y*1700)) for p in points]
                for chain in ((0,1,2,3,4),(0,5,6,7,8),(0,9,10,11,12),(0,13,14,15,16),(0,17,18,19,20),(5,9,13,17)):
                    for a,b in zip(chain,chain[1:]):
                        cv2.line(image,pix[a],pix[b],(130,230,170),3,cv2.LINE_AA)
                for xy in pix:
                    cv2.circle(image,xy,4,(240,240,240),-1)
                banner = 'SYNTHETIC INPUT - not camera accuracy validation'
            packet = controller.update(points, measured, t)
            if args.samples is None:
                if i==11 and not controller.calibrate_fingers('open'):
                    raise RuntimeError('Synthetic open calibration failed')
                if i==23 and not controller.calibrate_fingers('fist'):
                    raise RuntimeError('Synthetic fist calibration failed')
                if i==24:
                    controller.calibrate_wrist()
                    controller.capture_origin()
            log.write(json.dumps(packet,allow_nan=False)+'\n')
            counts['frames'] += 1
            for name in ('fingers','wrist','arm'):
                counts[name+'_valid'] += int(packet[name]['valid'])
            image=cv2.resize(image,(640,480))
            cv2.rectangle(image,(0,0),(640,40),(20,20,20),-1)
            cv2.putText(image,banner,(10,25),cv2.FONT_HERSHEY_SIMPLEX,.5,(80,210,255),1,cv2.LINE_AA)
            display=np.hstack((image,draw_unified_panel(packet,controller.model)))
            # Every sampled image gets one playback second. Keep acquisition t
            # unchanged for inference, controller and log (not real-time playback).
            video.write(display, i * 1000 if args.samples else t)
            if i == (100 if args.samples is None else len(files)//2):
                cv2.imwrite(str(args.output/'preview.png'),display)
        report=dict(counts, mode='recorded_samples_uncalibrated' if args.samples else 'synthetic_demo',
                    simulation_only=True,hardware_enabled=False, model=controller.model.config,
                    note='Recorded replay reruns world landmark detection and displays recorded depth; no user calibrations. Synthetic mode validates behavior, not measurement accuracy.')
        (args.output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(counts))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=Path,help='Optional recorded .depth-samples directory')
    parser.add_argument('--output',type=Path,required=True,help='New output directory')
    run(parser.parse_args())
