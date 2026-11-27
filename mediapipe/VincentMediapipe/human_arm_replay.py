"""Replay raw D455 samples through human-arm Pose detection, without opening USB."""
import argparse
from contextlib import ExitStack
import csv
import json
from pathlib import Path
import cv2
import mediapipe as mp
import numpy as np
import pyrealsense2 as rs
from human_arm import HumanArmTracker,select_pose,HUMAN_ARM_FIELDS,write_human_arm_csv,hand_wrists_from_result
from human_arm_view import draw_human_arm_overlay,draw_human_arm_depth
from recording import VideoRecorder


def run(samples,output,pose_model,metadata,hand_assistance=True,hand_model=None):
    files=sorted(samples.glob('*.json'))
    if not files:
        raise ValueError('No diagnostic samples found')
    camera=json.loads(metadata.read_text())
    if camera.get('aligned_to')!='color' or camera.get('units')!='m':
        raise ValueError('Expected color-aligned metric depth metadata')
    intrinsics=rs.intrinsics()
    for key,value in camera['intrinsics'].items():
        setattr(intrinsics,key,value)
    intrinsics.model=getattr(rs.distortion,camera['distortion_model'].split('.')[-1])
    output.mkdir(parents=True,exist_ok=False)
    counts=dict(frames=0,right_visible_complete=0,right_depth_complete=0,right_geometry_valid=0)
    options=mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(pose_model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=2,
        min_pose_detection_confidence=.6,min_pose_presence_confidence=.6,min_tracking_confidence=.6)
    tracker=HumanArmTracker()
    with ExitStack() as stack:
        detector=stack.enter_context(mp.tasks.vision.PoseLandmarker.create_from_options(options))
        hand_detector=None
        if hand_assistance:
            hand_options=mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(hand_model or Path(__file__).resolve().parent.parent/'models/hand_landmarker.task')),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=2,
                min_hand_detection_confidence=.6,min_hand_presence_confidence=.6,min_tracking_confidence=.6)
            hand_detector=stack.enter_context(mp.tasks.vision.HandLandmarker.create_from_options(hand_options))
        log=stack.enter_context((output/'human-arm.jsonl').open('x'))
        csvfile=stack.enter_context((output/'human-arm.csv').open('x',newline=''))
        writer=csv.DictWriter(csvfile,fieldnames=HUMAN_ARM_FIELDS);writer.writeheader()
        video=VideoRecorder(output/'preview.mp4',1,(1280,480));stack.callback(video.close)
        for i,path in enumerate(files):
            saved=json.loads(path.read_text())
            with np.load(path.with_suffix('.npz')) as arrays:
                image=arrays['color_bgr'].copy();raw=arrays['depth_z16'].copy();scale=float(arrays['meters_per_unit'])
            if image.shape[:2]!=raw.shape or raw.shape!=(intrinsics.height,intrinsics.width):
                raise ValueError('RGB/depth size does not match recorded calibration')
            t=int(saved['timestamp_ms'])
            mp_image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
            result=detector.detect_for_video(mp_image,t)
            index=select_pose(result)
            landmarks=None if index is None else result.pose_landmarks[index]
            hand_wrists=[]
            recorded_candidates=saved.get('human_arm',{}).get('hand_wrist_candidates')
            if hand_detector is not None:
                if recorded_candidates is not None:
                    hand_wrists=recorded_candidates
                else:
                    hand_wrists=hand_wrists_from_result(hand_detector.detect_for_video(mp_image,t))
            frame=tracker.update(landmarks,t,raw,scale,lambda pixel,z:rs.rs2_deproject_pixel_to_point(intrinsics,pixel,z),hand_wrists=hand_wrists)
            log.write(json.dumps(frame,allow_nan=False)+'\n');write_human_arm_csv(writer,frame)
            counts['frames']+=1
            right=[frame['points']['Right_'+j] for j in ('Shoulder','Elbow','Wrist')]
            counts['right_visible_complete']+=int(all(p['visible'] for p in right))
            counts['right_depth_complete']+=int(all(p['valid'] for p in right))
            counts['right_geometry_valid']+=int(frame['arms']['Right']['valid'])
            display=cv2.flip(image,1);draw_human_arm_overlay(display,frame,0)
            depth=cv2.applyColorMap(cv2.convertScaleAbs(raw,alpha=.04),cv2.COLORMAP_JET)
            depth=cv2.flip(depth,1);draw_human_arm_depth(depth,frame)
            display=np.hstack((display,depth))
            cv2.putText(display,'RECORDED: one sample per playback second',(10,52),cv2.FONT_HERSHEY_SIMPLEX,.43,(50,220,255),1,cv2.LINE_AA)
            video.write(display,i*1000)
            if i==len(files)//2:
                cv2.imwrite(str(output/'preview.png'),display)
        (output/'summary.json').write_text(json.dumps(dict(counts,hardware_enabled=False,
            sampling='Same conservative center-valid 3x3 sampling as live D455',
            pose_model=pose_model.name,hand_assistance=hand_assistance,
            hand_assistance_source="recorded_all_candidates_if_available_else_fresh_inference" if hand_assistance else "disabled",
            note='No ground-truth anatomical position or accuracy measurement; clothing/skin surface depth.'),indent=2))
    print(json.dumps(counts))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--metadata',type=Path,help='Recorded .depth.json; inferred from sample directory by default')
    parser.add_argument('--pose-model',type=Path,default=Path(__file__).resolve().parent.parent/'models/pose_landmarker_lite.task')
    parser.add_argument("--no-hand-assistance",action="store_true",help="Baseline comparison without hand-wrist support")
    args=parser.parse_args()
    metadata=args.metadata or args.samples.with_name(args.samples.name.removesuffix('.depth-samples')+'.depth.json')
    run(args.samples,args.output,args.pose_model,metadata,hand_assistance=not args.no_hand_assistance)
