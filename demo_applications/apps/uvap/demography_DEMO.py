import numpy as np
import argparse
import cv2
from confluent_kafka.cimpl import Producer

from utils.kafka.time_ordered_generator_with_timeout import TimeOrderedGeneratorWithTimeout, TopicInfo
from utils.uvap.graphics import draw_overlay, Position, draw_nice_bounding_box, draw_nice_text
from utils.uvap.uvap import message_list_to_frame_structure, encode_image_to_message


def main():
    parser = argparse.ArgumentParser(
        epilog=
        """Description:
           Plays a video from a jpeg topic,
           visualizes the head detection with an orage bounding box around a head
           and writes demography data (gender & age) data above the heads.
           Displays ('-d') or stores ('-o') the result of this demo in the kafka topic.
           
           Required topics:
           - <prefix>.cam.0.lowres.Image.jpg
           - <prefix>.cam.0.dets.ObjectDetectionRecord.json
           - <prefix>.cam.0.genders.GenderRecord.json
           - <prefix>.cam.0.ages.AgeRecord.json
           """
        , formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("broker", help="The name of the kafka broker.", type=str)
    parser.add_argument("prefix", help="Prefix of topics (base|skeleton).", type=str)
    parser.add_argument('-f', "--full_screen", action='store_true')
    parser.add_argument('-d', "--display", action='store_true')
    parser.add_argument('-o', '--output', help='write output image into kafka topic', action='store_true')
    args = parser.parse_args()

    if not args.display and not args.output:
        parser.error("Missing argument: -d (display output) or -o (write output to kafka) is needed")

    if args.output:
        producer = Producer({'bootstrap.servers': args.broker})

    overlay = cv2.imread('resources/powered_by_white.png', cv2.IMREAD_UNCHANGED)

    image_topic = f"{args.prefix}.cam.0.lowres.Image.jpg"
    detection_topic = f"{args.prefix}.cam.0.dets.ObjectDetectionRecord.json"
    gender_topic = f"{args.prefix}.cam.0.genders.GenderRecord.json"
    age_topic = f"{args.prefix}.cam.0.ages.AgeRecord.json"
    output_topic_name = f"{args.prefix}.cam.0.demography.Image.jpg"

    # handle full screen
    window_name = "DEMO: Demography (gender & age)"
    if args.full_screen:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # read message, draw and display them
    consumer = TimeOrderedGeneratorWithTimeout(
        args.broker,
        "detection",
        [
            TopicInfo(image_topic),
            TopicInfo(detection_topic),
            TopicInfo(gender_topic),
            TopicInfo(age_topic),
        ],
        100,
        None,
        True
    )

    i = 0
    for msgs in consumer.getMessage():
        for time, v in message_list_to_frame_structure(msgs).items():
            img = v[args.prefix]["0"]["image"]
            if type(img) == np.ndarray:
                for head_detection in v[args.prefix]["0"]["head_detection"]:
                    object_detection_record = v[args.prefix]["0"]["head_detection"][head_detection]["bounding_box"]
                    age_record = v[args.prefix]["0"]["head_detection"][head_detection]["age"]
                    gender_record = v[args.prefix]["0"]["head_detection"][head_detection]["gender"]
                    age = "" if age_record['age'] == {} else age_record['age']
                    gender = "" if gender_record['gender'] == {} else gender_record['gender']
                    # draw bounding_box
                    img = draw_nice_bounding_box(
                        img,
                        object_detection_record["bounding_box"],
                        (10, 95, 255)
                    )
                    # write age and gender
                    img = draw_nice_text(
                        img,
                        str(gender) + " " + str(age),
                        object_detection_record["bounding_box"],
                        (10, 95, 255)
                    )
                # draw ultinous logo
                img = draw_overlay(img, overlay, Position.BOTTOM_RIGHT)

                # produce output topic
                if args.output:
                    producer.produce(output_topic_name, value=encode_image_to_message(img), timestamp=time)
                    producer.poll(0)
                    if i % 100 == 0:
                        producer.flush()
                    i += 1

                # display
                if args.display:
                    cv2.imshow(window_name, img)
        k = cv2.waitKey(33)
        if k == 113:  # The 'q' key to stop
            break
        elif k == -1:  # normally -1 returned,so don't print it
            continue
        else:
            print(f"Press 'q' key for EXIT!")


if __name__ == "__main__":
    main()
