# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with Kodi; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html

## Screensaver that displays a slideshow of pictures grouped by the date the pictures were created.

#  This Program uses the immich api to retrieve images from immich.
#  Pictures are selected from immich that were all taken on the same date.
#  A group of pictures from that date are displayed.
#  Another date is chosen, and another group of pictures are displayed, etc.

### Additional features:

#     1. Some information from each picture can be displayed by the screensaver.
#        - Image tags if they occur in the immich database or in the image file itself
#          - Headline
#          - Caption
#          - Sublocation, City, State/Province, Country
#        - The image date and time
#     2. The current time can be displayed on each slide.
#     3. If pictures are taken in "burst mode" with a camera, then you may have
#        dozens of pictures, with multiple occuring in the same second, that look
#        almost identical. This makes for a very boring slideshow if each slide is
#        shown for a few seconds. When there are many pictures taken very close
#        together in time, you can selkect to have the slideshow speed up so that
#        there is much less time between "burst mode" images.
#     4. If music is playing when the slideshow is running, information about the
#        currently playing music can be displayed.
#     5. Slides can be displayed dimmed.

import os
import glob
import sys
from datetime import datetime,timedelta,time
from collections import deque
import requests
import logging

import xbmc
import xbmcgui


import xbmcaddon
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
#import xbmcvfs
#ADDON_USERDATA_FOLDER = xbmcvfs.translatePath("special://profile/addon_data/"+ADDON_ID)+'/'

# Store the downloads in /tmp (ramdrive)
ADDON_USERDATA_FOLDER = "/tmp/kodi-immich-slideshow/"

if not os.path.exists(ADDON_USERDATA_FOLDER):
    os.makedirs(ADDON_USERDATA_FOLDER, exist_ok=True)
    
def log(msg, level=xbmc.LOGINFO):
        filename = os.path.basename(sys._getframe(1).f_code.co_filename)
        lineno  = str(sys._getframe(1).f_lineno)
        xbmc.log(str("[%s] line %5d in %s >> %s"%(ADDON.getAddonInfo('name'), int(lineno), filename, msg.__str__())), level)

# Formats that can be displayed in a slideshow
PICTURE_FORMATS = ('bmp', 'jpeg', 'jpg', 'gif', 'png', 'tiff', 'mng', 'ico', 'pcx', 'tga', 'webp')

# Slide transition
FADEOUT_EFFECT = [['conditional', 'effect=fade start=100 end=0 time=2500 reversible=false condition=true']]
FADEIN_EFFECT  = [['conditional', 'effect=fade start=0 end=100 time=2500 reversible=false condition=true']]
# Burst mode transition
NO_EFFECT = []

IMMICH_TEMP_FILE_EXTENSION = '.immich-tmp'

IMG_SIZE = "preview"
global_filter = {"isFavorite": True, "isMotion": False, "type": "IMAGE"}

# use system settings for date and time format
date_fmt = xbmc.getRegion('dateshort')
time_fmt = xbmc.getRegion('time')

class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.last_album_ids = deque(maxlen=5)
        
        pass

    def onInit(self):
        try:
            # Init the monitor class to catch onscreensaverdeactivated calls
            self.Monitor = MyMonitor(action = self._exit)
            # Get addon settings
            self._get_settings()
             # Set UI Component information
            self._set_ui_controls()
            # Start the show
            self.stop = False
            self._start_show()
        # Catch communication exceptions
        except SlideshowException as se:
            text = '[B]'+se.header+'[/B]'+'\n'+se.message+'\n'
            for key, value in se.network_response.items():
                text = text+key+': '+str(value)+'\n'
            xbmc.executebuiltin("Dialog.Close(all)")
            dialog = xbmcgui.Dialog()
            dialog.ok(ADDON_ID, text)
        finally:
            # Delete any temporary image files that have been retrieved
            self._delete_temporary_files(exiting=True)

    def _get_settings(self):
        # Read addon settings
        self.slideshow_URL = ADDON.getSetting('URL')
        self.slideshow_APIKey = ADDON.getSetting('APIKey')
        self.slideshow_time = ADDON.getSettingInt('time')
        self.slideshow_limit = ADDON.getSettingInt('limit')
        self.slideshow_date = ADDON.getSettingBool('date')
        self.slideshow_tags = ADDON.getSettingBool('tags')
        self.slideshow_music = ADDON.getSettingBool('music')
        self.slideshow_clock = ADDON.getSettingBool('clock')
        self.slideshow_burst = ADDON.getSettingBool('burst')
        # convert float to hex value usable by the skin
        self.slideshow_dim = hex(int('%.0f' % (float(ADDON.getSettingInt('level')) * 2.55)))[2:] + 'ffffff'

    def _set_ui_controls(self):
        # Get the screensaver window id
        self.winid = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        # Get image controls from the xml
        self.image_control1 = self.getControl(1)
        self.image_control2 = self.getControl(2)
        self.background_image1 = self.getControl(3)
        self.background_image2 = self.getControl(4)
        # set the dim property
        self._set_prop('Dim', self.slideshow_dim)
        # show music info during slideshow if enabled
        if self.slideshow_music:
            self._set_prop('Music', 'show')
        # show clock if enabled
        if self.slideshow_clock:
            self._set_prop('Clock', 'show')
        # Set the skin name so we can have different looks for different skins
        self._set_prop('SkinName',xbmc.getSkinDir())

    def _start_show(self):
        # start with image 1
        current_image_control = self.image_control1
        order = [1,2]
        # fastmode is true when we find pictures taken in burst mode
        fastmode = False
        # loop until onScreensaverDeactivated is called
        while (not self.Monitor.abortRequested()) and (not self.stop):
            # Get the next grouping of pictures
            image_groupings = self._get_image_groupings()
            for image_group in image_groupings:
                # Delete any temporary image files that have been retrieved
                self._delete_temporary_files()
                fastmode = True if (len(image_group) > 2 and self.slideshow_burst) else False
                if fastmode:
                    # Found a group of pictures taken in burst mode
                    # Transition as fast as possilble
                    timetowait = 0
                    # set animations
                    animation1 = NO_EFFECT
                    animation2 = NO_EFFECT
                    # Turn off background images
                    self.background_image1.setVisible(False)
                    # Only show label transition animation when changing to a new date
                    self._set_info_fields(image_group[0],transition=(image_group == image_groupings[0]))
                else:
                    # Normal transition time
                    timetowait = self.slideshow_time
                    # set animations
                    animation1 = FADEIN_EFFECT
                    animation2 = FADEOUT_EFFECT
                    # Turn on background images
                    self.background_image1.setVisible(True)
                    self.background_image2.setVisible(True)

                # iterate through all the images in the group
                for image in image_group:
                    local_img_name = ADDON_USERDATA_FOLDER + image["id"] + IMMICH_TEMP_FILE_EXTENSION
                    
                    my_IMG_SIZE = IMG_SIZE
                    if IMG_SIZE == "original" and not image["originalMimeType"].lower().endswith(PICTURE_FORMATS):
                        my_IMG_SIZE = "fullsize"
                    
                    if not self._download_picture(image["id"], local_img_name, my_IMG_SIZE):
                        # Download failed, go to next image
                        continue

                    if not fastmode:
                        # Add picture information to slide
                        # Only show label transition animation when changing to a new date
                        self._set_info_fields(image,transition=(image_group == image_groupings[0]))
                        # Add background image to gui
                        if order[0] == 1:
                            self.background_image1.setImage(local_img_name, False)
                        else:
                            self.background_image2.setImage(local_img_name, False)
                        # add fade anim to background images
                        self._set_prop('Fade%d' % order[0], '0')
                        self._set_prop('Fade%d' % order[1], '1')

                    # Show the slide
                     # About to show images, so turn off splash screen
                    self._set_prop('Splash', 'hide')
                    current_image_control.setAnimations(animation1)
                    current_image_control.setImage(local_img_name, False)

                    # define next image
                    if current_image_control == self.image_control1:
                        current_image_control = self.image_control2
                        order = [2,1]
                    else:
                        current_image_control = self.image_control1
                        order = [1,2]

                    # transition out the previous slide control
                    current_image_control.setAnimations(animation2)

                    # Always show the last slide of a group for requested amount of time (even for burst mode slides)
                    if image == image_group[-1]:
                        timetowait = self.slideshow_time

                    # display the image for the specified amount of time
                    count = timetowait
                    while (not self.Monitor.abortRequested()) and (not self.stop) and count > 0:
                        count -= 1
                        xbmc.sleep(1000)

                    # break out of the 'images in image_group loop' if onScreensaverDeactivated is called
                    if  self.stop or self.Monitor.abortRequested():
                        self.stop = True
                        break

                # break out of the 'image_group in image_groupings' loop if onScreensaverDeactivated is called
                if  self.stop or self.Monitor.abortRequested():
                    self.stop = True
                    break

    #----------------------------------------------------------------------
    def _get_image_groupings(self, update=False):

        max_tries = 10
        for _ in range(max_tries):

            # get random Asset
            d1 = self._get_random_Asset()[0]

            # is it part of an Album?
            a1 = self._getAllAlbums(d1['id'])          
            
            if not a1: # no Album
                break
                
            this_album_id = a1[0]['id']
            if this_album_id in self.last_album_ids:
                continue

            self.last_album_ids.append(this_album_id)
            break
            
            
        if a1:  # yes part of an album
            #print(a1[0]['albumName'])
        
            d2 = self._get_random_Asset({"size": self.slideshow_limit, 'albumIds': [this_album_id]})
            
            for x in d2:
                x["albumName"] = a1[0]['albumName']
                

        else: # no get some random pictures from the same day
            #print('no albums')
            # Get all of the pictures taken on the chosen date.

            this_dt = datetime.fromisoformat(d1['localDateTime'])

            d2 = self._get_random_Asset({
                "isNotInAlbum": True,
                "takenBefore":  datetime.combine(this_dt.date(), time.min, tzinfo=this_dt.tzinfo), 
                "takenAfter":   datetime.combine(this_dt.date(), time.max, tzinfo=this_dt.tzinfo), 
                "size":         self.slideshow_limit
                })

        logging.info(d2)

        all_images_for_date = self._Sort_Asset(d2)

        if len(all_images_for_date) == 0:
            # No displayable pictures found for this date
            return []

        # Group together pictures taken in burst mode
        group_index = 0
        # Put the first picture in the first group
        image_groupings=[[all_images_for_date[0]]]
        # Get date and time with milliseconds, but without time zone
        prev_image_date_object = datetime.fromisoformat(all_images_for_date[0]['localDateTime'])
        # Go through the rest of the images
        image_index = 1
        while image_index < len(all_images_for_date):
            # Get date and time with milliseconds, but without time zone
            this_image_date_object = datetime.fromisoformat(all_images_for_date[image_index]['localDateTime'])
            
            # Calculate difference between when this picture was taken and when the last picture was taken
            datediff = this_image_date_object - prev_image_date_object
            if datediff.total_seconds() <= 2:
                # image within two seconds of previous image go in same group
                image_groupings[group_index].append(all_images_for_date[image_index])
                if not self.slideshow_burst:
                    # Only store the first and last images if not showing them in burst mode
                    if len(image_groupings[group_index]) > 2:
                        image_groupings[group_index].pop(1)
            else:
                # Insert a singleton of first burst image so it pauses before starting the burst
                if len(image_groupings[group_index]) > 2:
                    image_groupings.insert(group_index,[image_groupings[group_index][0]])
                    group_index +=1
                # image greater than two seconds from previous image go in a new group
                group_index += 1
                image_groupings.append([all_images_for_date[image_index]])
            prev_image_date_object = this_image_date_object
            image_index+=1

        # Return the requested number of pictures
        return image_groupings

    #----------------------------------------------------------------------
    def _set_info_fields(self, image, transition=True):
        # Get info about the image
        info = self._get_image_info(image)

        # Transition between two sets of info if requested
        if transition:
            self._set_prop('FadeoutLabels' ,'1')
            xbmc.sleep(750)

        # Assign whatever info was found into the correct labels
        for x in ['Headline', 'Caption', 'Sublocation', 'City', 'State', 'Country', 'Date', 'Time']:
            if x in info:
                self._set_prop(x, info[x])
            else:
                self._clear_prop(x)

        # Complete the transition to the new set of info
        if transition:
            self._set_prop('FadeinLabels', '1')
            xbmc.sleep(750)
        self._set_prop('FadeoutLabels', '0')

    #----------------------------------------------------------------------
    def _get_image_info(self, image):
        immich_info = {}

        # Get all of the info for this image
        if self.slideshow_date:
            # Get the date and time the image was taken
            dt = datetime.fromisoformat(image['localDateTime'])
            immich_info['Date'] = dt.strftime(date_fmt)
            immich_info['Time'] = dt.strftime(time_fmt)
        if self.slideshow_tags:
            # Get info about image from the immich API
            AssetInfo = self._getAssetInfo(image["id"])
            exifinfo = AssetInfo['exifInfo']
            immich_info['Country']  = exifinfo['country']
            immich_info['State']    = exifinfo['state']
            immich_info['City']     = exifinfo['city']
            immich_info['Caption']  = exifinfo['description']
            immich_info['Headline'] = AssetInfo['originalFileName']
            
        if 'albumName' in image:
            immich_info['Headline'] = image['albumName']
            
#            # Get more info from the actual file.
#            iptc_info = self._get_iptcinfo(self._get_local_filename_for_image(image))
        # Info in file (iptc_info) overrides info from immich (immich_info)
 #       image_info = {**immich_info, **iptc_info}
        image_info = immich_info
        return image_info

    # ---------------------------------------------------------------------------
    def _download_picture(self, image_uuid, local_filename, size="preview"):
        # size: [original, fullsize, preview, thumbnail]
        # preview: 1440p

        if size=="original":
            url = f"{self.slideshow_URL}/api/assets/{image_uuid}/original"
        else:
            url = f"{self.slideshow_URL}/api/assets/{image_uuid}/thumbnail?size={size}"

        headers = {
            "x-api-key": self.slideshow_APIKey,
            "Accept": "application/octet-stream"
            }
            
        try:
            with requests.get(url, stream=True, headers=headers) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            attempts = 0
            while not os.path.exists(local_filename):
                xbmc.sleep(100)
                attempts += 1
                if attempts > 5:
                    return False
            return True
        except:
            return False
			
    #---------------------------------------------------------
    def _delete_temporary_files(self, exiting=False):
        try:
            for filename in glob.glob(ADDON_USERDATA_FOLDER+'*'+IMMICH_TEMP_FILE_EXTENSION):
                if exiting or (os.path.getmtime(filename) < (datetime.now()- timedelta(hours=3))):
                    os.remove(filename)
        except:
            pass

    #---------------------------------------------------------
    def _api_call(self, action, path, payload=None):
        response = {}
        try:
            url = f"{self.slideshow_URL}/api/{path}"
        
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-api-key': self.slideshow_APIKey
            }
            
            resp = requests.request(action, url, headers=headers, json=payload)
            response = resp.json()
            
            if resp.status_code == 401:
                self.stop = True;
                raise SlideshowException(ADDON.getLocalizedString(30420),ADDON.getLocalizedString(30430),response)
            elif resp.status_code != 200:
                self.stop = True;
                raise SlideshowException(ADDON.getLocalizedString(30400),ADDON.getLocalizedString(30410),response)
        except SlideshowException:
            raise
        except requests.exceptions.ConnectionError as ce:
            raise SlideshowException(ADDON.getLocalizedString(30400), str(ce))
        return response

    #---------------------------------------------------------
    def _get_random_Asset(self, filter={"size": 1}):    
	    # Just get one random picture
	    
	    d = global_filter.copy()
	    d.update(filter)
	    
	    response = self._api_call("POST", "search/random", d)
	    return response
	    
    #---------------------------------------------------------
    def _Sort_Asset(self, indata, sortkey='localDateTime'):
	    return sorted(indata, key=lambda d: d[sortkey])
	    
    #---------------------------------------------------------
    def _getAllAlbums(self, assetId):
	    response = self._api_call("GET", f"albums?assetId={assetId}")
	    
	    blacklist = ['Bilderrahmen']
	    	    
	    data = [x for x in response if x['albumName'] not in blacklist]
	    return data
	    
    #---------------------------------------------------------
    def _getAssetInfo(self, assetId):
	    return self._api_call("GET", f"assets/{assetId}")

    #---------------------------------------------------------
    def _set_prop(self, name, value):
        self.winid.setProperty('Screensaver.%s' % name, value)

    def _clear_prop(self, name):
        self.winid.clearProperty('Screensaver.%s' % name)

    def _exit(self):
        # exit when onScreensaverDeactivated gets called
        self.stop = True
        # clear our properties on exit
        self._clear_prop('Fade1')
        self._clear_prop('Fade2')
        self._clear_prop('FadeinLabels')
        self._clear_prop('FadeoutLabels')
        self._clear_prop('Dim')
        self._clear_prop('Music')
        self._clear_prop('Clock')
        self._clear_prop('Splash')
        self._clear_prop('SkinName')
        for x in ['Headline', 'Caption', 'Sublocation', 'City', 'State', 'Country', 'Date', 'Time']:
             self._clear_prop(x)
        self.close()

class SlideshowException(Exception):
    def __init__(self,header,message,network_response={}):
        self.header = header
        self.message = message
        self.network_response = network_response

# Notify when screensaver is to stop
class MyMonitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        self.action = kwargs['action']

    def onScreensaverDeactivated(self):
        self.action()

    def onDPMSActivated(self):
        self.action()


    
