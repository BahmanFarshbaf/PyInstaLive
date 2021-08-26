import os
import shutil
import re
import glob
import subprocess
import json
import sys
try:
    import pil
    import logger
    import helpers
    from constants import Constants
except ImportError:
    from . import pil
    from . import logger
    from . import helpers
    from .constants import Constants

"""
The content of this file was originally written by https://github.com/taengstagram
The code has been edited for use in PyInstaLive.
"""


def _get_file_index(filename):
    """ Extract the numbered index in filename for sorting """
    mobj = re.match(r'.+\-(?P<idx>[0-9]+)\.[a-z]+', filename)
    if mobj:
        return int(mobj.group('idx'))
    return -1


def assemble(user_called=True, retry_with_zero_m4v=False):
    try:
        ass_json_file = pil.assemble_arg if pil.assemble_arg.endswith(".json") else pil.assemble_arg + ".json"
        ass_mp4_file = os.path.join(pil.dl_path, os.path.basename(ass_json_file).replace("_downloads", "").replace(".json", ".mp4"))
        ass_segment_dir = pil.assemble_arg if not pil.assemble_arg.endswith(".json") else pil.assemble_arg.replace(".json", "")
        
        livestream_info = {}
        if not os.path.isdir(ass_segment_dir):
            logger.error("Could not create video file: The segment directory does not exist.")
            logger.separator()
            return False
        elif not os.listdir(ass_segment_dir):
            logger.error("Could not create video file: The segment directory does not contain any files.")
            logger.separator()
            return False
        
        if not os.path.isfile(ass_json_file):
            logger.warn("No matching JSON file found for the segment directory, trying to continue without it.")
            ass_stream_id = os.listdir(ass_segment_dir)[0].split('-')[0]
            livestream_info["broadcast_dict"]['id'] = ass_stream_id
            livestream_info["broadcast_dict"]['broadcast_status'] = "active"
            livestream_info['segments'] = {}
        else:
            with open(ass_json_file) as info_file:
                try:
                    livestream_info = json.load(info_file)
                except Exception as e:
                    logger.warn("Could not decode JSON file, trying to continue without it.")
                    ass_stream_id = os.listdir(ass_segment_dir)[0].split('-')[0]
                    livestream_info["broadcast_dict"]['id'] = ass_stream_id
                    livestream_info["broadcast_dict"]['broadcast_status'] = "active"
                    livestream_info['segments'] = {}

        stream_id = str(livestream_info["broadcast_dict"]['id'])

        segment_meta = livestream_info.get('segments', {})
        if segment_meta:
            all_segments = [
                os.path.join(ass_segment_dir, k)
                for k in livestream_info['segments'].keys()]
        else:
            all_segments = list(filter(
                os.path.isfile,
                glob.glob(os.path.join(ass_segment_dir, '%s-*.m4v' % stream_id))))

        all_segments = sorted(all_segments, key=lambda x: _get_file_index(x))
        sources = []
        audio_stream_format = 'assembled_source_{0}_{1}_mp4.tmp'
        video_stream_format = 'assembled_source_{0}_{1}_m4a.tmp'
        video_stream = ''
        audio_stream = ''
        has_skipped_zero_m4v = False

        if not all_segments:
            logger.error("Could not create video file: The segment directory does not contain any files.")
            logger.separator()
            return False

        for segment in all_segments:
            segment = re.sub('\?.*$', '', segment)
            if not os.path.isfile(segment.replace('.m4v', '.m4a')):
                logger.warn('Audio segment not found: {0!s}'.format(segment.replace('.m4v', '.m4a')))
                continue

            if segment.endswith('-init.m4v'):
                logger.info('Replacing %s' % segment)
                segment = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)), 'repair', 'init.m4v')

            if segment.endswith('-0.m4v') and not retry_with_zero_m4v:
                has_skipped_zero_m4v = True
                continue

            video_stream = os.path.join(
                ass_segment_dir, video_stream_format.format(stream_id, len(sources)))
            audio_stream = os.path.join(
                ass_segment_dir, audio_stream_format.format(stream_id, len(sources)))


            file_mode = 'ab'

            with open(video_stream, file_mode) as outfile, open(segment, 'rb') as readfile:
                shutil.copyfileobj(readfile, outfile)

            with open(audio_stream, file_mode) as outfile, open(segment.replace('.m4v', '.m4a'), 'rb') as readfile:
                shutil.copyfileobj(readfile, outfile)

        if audio_stream and video_stream:
            sources.append({'video': video_stream, 'audio': audio_stream})

        for n, source in enumerate(sources):
            ffmpeg_binary = os.getenv('FFMPEG_BINARY', 'ffmpeg')
            cmd = [
                ffmpeg_binary, '-loglevel', 'error', '-y',
                '-i', source['audio'],
                '-i', source['video'],
                '-c:v', 'copy', '-c:a', 'copy', ass_mp4_file]
            #fnull = open(os.devnull, 'w')
            fnull = None
            exit_code = subprocess.call(cmd, stdout=fnull, stderr=subprocess.STDOUT)
            if exit_code != 0:
                logger.warn("FFmpeg exit code not '0' but '{:d}'.".format(exit_code))
                if has_skipped_zero_m4v and not retry_with_zero_m4v:
                    logger.binfo("*-0.m4v segment was detected but skipped, retrying to assemble video without "
                                 "skipping it.")
                    os.remove(source['audio'])
                    os.remove(source['video'])
                    logger.separator()
                    return assemble(user_called, retry_with_zero_m4v=True)
                    
            else:
                os.remove(source['audio'])
                os.remove(source['video'])
            if user_called:
                logger.info('Created video: %s' % os.path.basename(ass_mp4_file))
                logger.separator()
            return True
    except Exception as e:
        logger.error("Could not create video file: {:s}".format(str(e)))
