#!/usr/bin/env python3
from typing import Optional

import rospy
from jsk_recognition_msgs.msg import LabelArray, VectorArray
from node_config import NodeConfig
from rospy import Publisher, Subscriber
from sensor_msgs.msg import Image
from wrapper import DeticWrapper

from detic_ros.msg import SegmentationInfo
from detic_ros.srv import DeticSeg, DeticSegRequest, DeticSegResponse


class DeticRosNode:
    detic_wrapper: DeticWrapper
    sub: Subscriber
    # some debug image publisher
    pub_debug_image: Optional[Publisher]
    pub_debug_segmentation_image: Optional[Publisher]

    # used when you set use_jsk_msgs = True
    pub_segimg: Optional[Publisher]
    pub_labels: Optional[Publisher]
    pub_score: Optional[Publisher]

    # otherwise, the following publisher will be used
    pub_info: Optional[Publisher]

    def __init__(self, node_config: Optional[NodeConfig] = None):
        if node_config is None:
            node_config = NodeConfig.from_rosparam()

        self.detic_wrapper = DeticWrapper(node_config)
        self.srv_handler = rospy.Service('~segment_image', DeticSeg, self.callback_srv)

        if node_config.enable_pubsub:
            # As for large buff_size please see:
            # https://answers.ros.org/question/220502/image-subscriber-lag-despite-queue-1/?answer=220505?answer=220505#post-id-22050://answers.ros.org/question/220502/image-subscriber-lag-despite-queue-1/?answer=220505?answer=220505#post-id-220505
            self.sub = rospy.Subscriber('~input_image', Image, self.callback_image, queue_size=1, buff_size=2**24)
            if node_config.use_jsk_msgs:
                self.pub_segimg = rospy.Publisher('~segmentation', Image, queue_size=1)
                self.pub_labels = rospy.Publisher('~detected_classes', LabelArray, queue_size=1)
                self.pub_score = rospy.Publisher('~score', VectorArray, queue_size=1)
            else:
                self.pub_info = rospy.Publisher('~segmentation_info', SegmentationInfo,
                                                queue_size=1)

            if node_config.out_debug_img:
                self.pub_debug_image = rospy.Publisher('~debug_image', Image, queue_size=1)
            else:
                self.pub_debug_image = None
            if node_config.out_debug_segimg:
                self.pub_debug_segmentation_image = rospy.Publisher('~debug_segmentation_image',
                                                                    Image, queue_size=10)
            else:
                self.pub_debug_segmentation_image = None

        rospy.loginfo('initialized node')

    def callback_image(self, msg: Image):
        # Inference
        raw_result = self.detic_wrapper.infer(msg)

        # Publish main topics
        if self.detic_wrapper.node_config.use_jsk_msgs:
            # assertion for mypy
            assert self.pub_segimg is not None
            assert self.pub_labels is not None
            assert self.pub_score is not None
            seg_img = raw_result.get_ros_segmentaion_image()
            labels = raw_result.get_label_array()
            scores = raw_result.get_score_array()
            self.pub_segimg.publish(seg_img)
            self.pub_labels.publish(labels)
            self.pub_score.publish(scores)
        else:
            assert self.pub_info is not None
            seg_info = raw_result.get_segmentation_info()
            self.pub_info.publish(seg_info)

        # Publish optional topics

        if self.pub_debug_image is not None:
            debug_img = raw_result.get_ros_debug_image()
            self.pub_debug_image.publish(debug_img)

        if self.pub_debug_segmentation_image is not None:
            debug_seg_img = raw_result.get_ros_debug_segmentation_img()
            self.pub_debug_segmentation_image.publish(debug_seg_img)

        # Print debug info
        if self.detic_wrapper.node_config.verbose:
            time_elapsed_total = (rospy.Time.now() - msg.header.stamp).to_sec()
            rospy.loginfo('total elapsed time in callback {}'.format(time_elapsed_total))

    def callback_srv(self, req: DeticSegRequest) -> DeticSegResponse:
        msg = req.image
        raw_result = self.detic_wrapper.infer(msg)
        seginfo = raw_result.get_segmentation_info()

        resp = DeticSegResponse()
        resp.seg_info = seginfo

        if raw_result.visualization is not None:
            debug_image = raw_result.get_ros_debug_segmentation_img()
            resp.debug_image = debug_image
        return resp


if __name__ == '__main__':
    rospy.init_node('detic_node', anonymous=True)
    node = DeticRosNode()
    rospy.spin()
