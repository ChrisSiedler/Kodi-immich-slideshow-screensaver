#!/usr/bin/env python3

import requests
import logging
import sys
from lib.models import Album, ItemAsset, TimelineBucket

class Immich_API():
    def __init__(self, RAW_SERVER_URL, APIKey):
        self.url    = RAW_SERVER_URL
        self.APIKey = APIKey
        self.global_filter = {}

    #---------------------------------------------------------
    @staticmethod
    def _user_agent():
        try:
            import xbmc
            return xbmc.getUserAgent()
        except ModuleNotFoundError:
            return "Immich-API 0.1"
            
    #---------------------------------------------------------
    def _api_call(self, action, path, payload=None):
        url = f"{self.url}/api/{path}"

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-api-key': self.APIKey,
            "User-agent": self._user_agent(),
            }

        resp = requests.request(action, url, headers=headers, json=payload)

        if resp.status_code == 401:
            return false

        elif resp.status_code != 200:
            return false
            
        response = resp.json()
        return response

    #---------------------------------------------------------
    def get_version(self):
        return self._api_call("GET", "server/version")

    #---------------------------------------------------------
    def getAllAlbums(self):
        resp = self._api_call("GET", "albums")
        return [Album.from_api_response(d) for d in resp ]
        
    #---------------------------------------------------------
    def getTimeBuckets(self):
        resp = self._api_call("GET", "timeline/buckets")
        return [TimelineBucket.from_api_response(d) for d in resp ]

    #---------------------------------------------------------
    def getThumbUrl(self, uuid):
        return self.getAssetUrl(uuid, size="preview")

    def getAssetUrl(self, uuid, size="original"):
        if size=="original":
            return f"{self.url}/api/assets/{uuid}/original|x-api-key={self.APIKey}"
            
        elif size=="preview":
            return f"{self.url}/api/assets/{uuid}/thumbnail?size={size}|x-api-key={self.APIKey}"
        else:
            raise ValueError
    #---------------------------------------------------------
    def get_album(self, id):
   
        resp = self._api_call("POST", "search/metadata", {
            "albumIds": [id],
            "visibility": "timeline",
            "withExif": True
            })
            
        data = {"assets": [ItemAsset.from_api_response(d) for d in resp["assets"]["items"]]}
        return data

    #---------------------------------------------------------
    def getTimeBucket(self, startdate, enddate):
        
        resp = self._api_call("POST", "search/metadata", {
            "visibility": "timeline",
            "withExif": True,
            "takenAfter": startdate.isoformat(), 
            "takenBefore": enddate.isoformat()
            })
        
        data = {"assets": [ItemAsset.from_api_response(d) for d in resp["assets"]["items"]]}
        return data

    #---------------------------------------------------------
    def get_random_Asset(self, filter={"size": 1}):    
        # Just get one random picture

        d = self.global_filter.copy()
        d.update(filter)

        response = self._api_call("POST", "search/random", d)
        return response
        
    #---------------------------------------------------------
    def getAssetInfo(self, assetId):
	    return self._api_call("GET", f"assets/{assetId}")

    #---------------------------------------------------------
    def getParrentAlbums(self, assetId):
	    response = self._api_call("GET", f"albums?assetId={assetId}")
	    
	    blacklist = ['Bilderrahmen']
	    	    
	    data = [x for x in response if x['albumName'] not in blacklist]
	    return data
	    

# ======================================================================================
# ======================================================================================
    
