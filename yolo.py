import numpy as np
import argparse
import cv2 as cv
import subprocess
import time
import pandas as pd
from yolo_utils import infer_image, show_image
from gaze_tracking import GazeTracking

FLAGS = []

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-m', '--model-path',
                        type=str,
                        default='./yolov3-coco/',
                        help='The directory where the model weights and configuration files are.')

    parser.add_argument('-w', '--weights',
                        type=str,
                        default='./yolov3-coco/yolov3.weights',
                        help='Path to the file which contains the weights for YOLOv3.')

    parser.add_argument('-cfg', '--config',
                        type=str,
                        default='./yolov3-coco/yolov3.cfg',
                        help='Path to the configuration file for the YOLOv3 model.')

    parser.add_argument('-i', '--image-path',
                        type=str,
                        help='The path to the image file')

    parser.add_argument('-v', '--video-path',
                        type=str,
                        help='The path to the video file')

    parser.add_argument('-vo', '--video-output-path',
                        type=str,
                        default='./output.avi',
                        help='The path of the output video file')

    parser.add_argument('-l', '--labels',
                        type=str,
                        default='./yolov3-coco/coco-labels',
                        help='Path to the file having the labels in a new-line separated way.')

    parser.add_argument('-c', '--confidence',
                        type=float,
                        default=0.5,
                        help='Model will reject boundaries which has probability less than the confidence value. '
                             'default: 0.5')

    parser.add_argument('-th', '--threshold',
                        type=float,
                        default=0.3,
                        help='The threshold to use when applying the Non-Max Suppression')

    parser.add_argument('--download-model',
                        type=bool,
                        default=False,
                        help='Set to True, if the model weights and configurations are not present on your local '
                             'machine.')

    parser.add_argument('-t', '--show-time',
                        type=bool,
                        default=False,
                        help='Show the time taken to infer each image.')

    FLAGS, unparsed = parser.parse_known_args()

    # Download the YOLOv3 models if needed
    if FLAGS.download_model:
        subprocess.call(['./yolov3-coco/get_model.sh'])

    # Get the labels
    labels = open(FLAGS.labels).read().strip().split('\n')

    # Initializing colors to represent each label uniquely
    colors = np.random.randint(0, 255, size=(len(labels), 3), dtype='uint8')

    # Load the weights and configuration to form the pretrained YOLOv3 model
    net = cv.dnn.readNetFromDarknet(FLAGS.config, FLAGS.weights)

    # Get the output layer names of the model
    layer_names = net.getLayerNames()
    layer_names = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]

    # If both image and video files are given then raise error
    if FLAGS.image_path is None and FLAGS.video_path is None:
        print('Neither path to an image or path to video provided')
        print('Starting Inference on Webcam')

    # Do inference with given image
    if FLAGS.image_path:
        # Read the image
        try:
            img = cv.imread(FLAGS.image_path)
            height, width = img.shape[:2]
        except:
            raise Exception('Image cannot be loaded!\n\
                               Please check the path provided!')

        finally:
            img, _, _, _, _ = infer_image(net, layer_names, height, width, img, colors, labels, FLAGS)
            show_image(img)

    elif FLAGS.video_path:
        # Read the video
        try:
            vid = cv.VideoCapture(FLAGS.video_path)
            height, width = None, None
            writer = None
        except:
            raise Exception('Video cannot be loaded!\n\
                               Please check the path provided!')

        finally:
            while True:
                grabbed, frame = vid.read()

                # Checking if the complete video is read
                if not grabbed:
                    break

                if width is None or height is None:
                    height, width = frame.shape[:2]

                frame, _, _, _, _ = infer_image(net, layer_names, height, width, frame, colors, labels, FLAGS)

                if writer is None:
                    # Initialize the video writer
                    fourcc = cv.VideoWriter_fourcc(*"MJPG")
                    writer = cv.VideoWriter(FLAGS.video_output_path, fourcc, 30,
                                            (frame.shape[1], frame.shape[0]), True)

                writer.write(frame)

            print("[INFO] Cleaning up...")
            writer.release()
            vid.release()

    else:
        # Infer real-time on webcam
        count = 0
        e1 = cv.getTickCount()
        vid = cv.VideoCapture(0)
        gaze = GazeTracking()
        df = pd.DataFrame(columns=['Object', 'Accuracy', 'Frame No', 'Yolo_Time', 'FPS'])

        pre_time = 0
        nxt_time = 0

        while True:
            _, frame = vid.read()
            height, width = frame.shape[:2]
            nxt_time = time.time()

            font = cv.FONT_HERSHEY_SIMPLEX
            fps = 1 / (nxt_time - pre_time)
            pre_time = nxt_time

            fps = float(fps)

            fps = str(fps)
            frame = gaze.annotated_frame()
            text = ""

            if gaze.is_blinking():
                text = "Blinking"
            elif gaze.is_right():
                text = "Looking right"
            elif gaze.is_left():
                text = "Looking left"
            elif gaze.is_center():
                text = "Looking center"

            cv.putText(frame, text, (5, 450), cv.FONT_HERSHEY_SIMPLEX, 0.5, (147, 58, 31), 1)
            left_pupil = gaze.pupil_left_coords()
            right_pupil = gaze.pupil_right_coords()
            cv.putText(frame, "Left pupil:  " + str(left_pupil), (5, 470), cv.FONT_HERSHEY_SIMPLEX, 0.5,
                       (147, 58, 31), 1)
            cv.putText(frame, "Right pupil: " + str(right_pupil), (255, 470), cv.FONT_HERSHEY_SIMPLEX, 0.5,
                       (147, 58, 31), 1)

            if count == 0:
                frame, boxes, confidences, classids, idxs, timex = infer_image(net, layer_names, height, width, frame, colors, labels, FLAGS)
                count += 1
                for i in range(len(confidences)):
                    print("Object : {} - Accuracy : {:4f} - Frame : {} - Yolo_Time = {}s - FPS = {}".format(
                        labels[classids[i]], confidences[i] * 100, count, timex, fps))
                    df.loc[len(df.index)] = [labels[classids[i]], confidences[i], count, timex, fps]
            else:
                frame, boxes, confidences, classids, idxs, timex = infer_image(net, layer_names, height, width, frame,
                                                                               colors, labels, FLAGS, boxes,
                                                                               confidences, classids, idxs, infer=False)
                count = (count + 1) % 6
                for i in range(len(confidences)):
                    print("Object : {} - Accuracy : {:4f} - Frame : {} - Yolo_Time = {}s - FPS = {}".format(
                        labels[classids[i]], confidences[i] * 100, count, timex, fps))
                    df.loc[len(df.index)] = [labels[classids[i]],
                                             confidences[i], count, timex, fps]
            cv.putText(frame, fps, (20, 75), font, 3, (100, 255, 0), 3, cv.LINE_AA)

            e2 = cv.getTickCount()
            time = (e2 - e1) / cv.getTickFrequency()
            cv.putText(frame, "Performance: " + str(time), (455, 470), cv.FONT_HERSHEY_SIMPLEX, 0.5, (147, 58, 31), 1)
            cv.imshow("Webcam Demonstration", frame)

            if cv.waitKey(1) & 0xFF == ord('q'):
                df.to_csv(r'logs.csv')
                break
        vid.release()
        cv.destroyAllWindows()
