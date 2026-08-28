//
// global array of message objects
var aMessages = new Array();
//
//  retrieve all messages from the messaging system and populate the array of message objects
function initMessaging()
{
	/* return the number of messages found */
	var nMessageCount = 0;

	/* itterate over the list of messages and create objects that we'll use to populate the list ctrl */
	var strMessageIDList = window.external.GetMessageIDList();
	var aMessageID = strMessageIDList.split(";");
	for(var itr = 0 ; itr < aMessageID.length ; itr++)
	{
		var strMsgID = aMessageID[itr];
		if ((strMsgID != null) && (strMsgID.length > 0))
		{
			/* use the message id to get the message from the host application */
			var xmlMessage = window.external.GetMessage(strMsgID);
			if(xmlMessage != null)
			{
				/* get the viewed state for the message */
				var bMessageViewed = false;
				if ( window.external.HasMessageBeenTracked(strMsgID, "Archive", "Click") 
				    || window.external.HasMessageBeenTracked(strMsgID, "Center", "Click") 
				    || window.external.HasMessageBeenTracked(strMsgID, "HTMLWnd", "Click") )
				{
				    bMessageViewed = true;
				}

				/* get the message title */
				var strMessageTitle = xmlMessage.getAttribute("title");

				/* get the message type */
				var strMessageType = xmlMessage.getAttribute("type");

				/* get the message width */
				var strMessageWidth = "190";
				var elmWidthNode = xmlMessage.selectSingleNode("contents/content[@type='body']/@width");
				if (null != elmWidthNode)
				{
				    strMessageWidth = elmWidthNode.text;
				}

				/* get the message height */
				var strMessageHeight = "190";
				var elmHeightNode = xmlMessage.selectSingleNode("contents/content[@type='body']/@height");
				if (null != elmHeightNode)
				{
				    strMessageHeight = elmHeightNode.text;
				}

				/* get the local URL to the message */
				var strURL = "about:blank";
				var elmUrlNode = xmlMessage.selectSingleNode("contents/content[@type='body']/@localpath");
				if(null != elmUrlNode)
				{
					strURL = elmUrlNode.text;
				}

				/* get the detail URL */
				var strDetail = "";
				elmUrlNode = xmlMessage.selectSingleNode("contents/content[@type='detail']/@localpath");
				if(null != elmUrlNode)
				{
					strDetail = elmUrlNode.text;
				}
                
                
				/* get the message subtypelevel1 */
				var strSubTypeLevel1 = xmlMessage.getAttribute("subtypelevel1");
				 
				/* construct a message object and store the object in the global array */
				var objMessage = new message(strMsgID, bMessageViewed, strMessageTitle, strMessageType, strURL, strDetail, strMessageWidth, strMessageHeight, strSubTypeLevel1);
				if(null != objMessage)
				{
					aMessages.push(objMessage);
					nMessageCount++;
				}
			}
		}	
	}

	return nMessageCount;
}

//
// construct a message object
function message(strID, bViewed, strTitle, strType, strURL, strDetail, strMessageWidth, strMessageHeight, strSubTypeLevel1)
{
	this.id = strID;
	this.bViewed = bViewed;
	this.strTitle = strTitle;
	this.strType = strType;
	this.strURL = strURL;
	this.strDetail = strDetail;
	this.strMessageWidth = strMessageWidth;
	this.strMessageHeight = strMessageHeight;
	this.strSubTypeLevel1 = strSubTypeLevel1;
}

//
// given a message id find the first message object with that id
function findMessageById(strID)
{
	var objRet = null;
	if((null != strID) && (strID.length > 0))
	{
		for( var itrMsg = 0 ; itrMsg < aMessages.length ; itrMsg++ )
		{
			if( aMessages[itrMsg].id == strID )
			{
				objRet = aMessages[itrMsg];
				break;
			}
		}
	}
	return objRet;
}

//
// find the first unread message in the message array
function findFirstUnreadMessage()
{
	var objRet = null;
	
	if(aMessages)
	{
		for( var itrMsg = 0 ; itrMsg < aMessages.length ; itrMsg++ )
		{
			if(! aMessages[itrMsg].bViewed )
			{
				objRet = aMessages[itrMsg];
				break;
			}
		}
	}
	
	return objRet;
}

//
// given a message ID get the XML dom that makes up the message
function XMLFromMsgID(strMsgID)
{
	var objDOM = null;
	
	if((strMsgID != null) && (strMsgID.length > 0))
	{
		objDOM = window.external.GetMessage(strMsgID);
	}
	
	return objDOM;
}

//
// Retrieves a given parameter from the URL string
// Note: This function has been copied from ccc.js.
// TBD: Refactor the shared scripts
//
function getParamVal(paramName)
{
	var sQueryVar = location.search.toLowerCase();
	return extractParam(sQueryVar, paramName);
}

//
// Extracts the given parameter from the given URL string
// Note: This function has been copied from ccc.js.
// TBD: Refactor the shared scripts
//
function extractParam(sQueryVar, paramName)
{
	if (sQueryVar == null || paramName == null)
		return "";

	var nIndex = sQueryVar.indexOf("?");
	if (nIndex >= 0)
		sQueryVar = sQueryVar.substr(nIndex + 1);

    paramName = paramName.toLowerCase();

    sQueryVar = sQueryVar.replace(/%26/g, "&");

    var asParams = sQueryVar.split("&");
    var i;

    for (i in asParams)
    {
		var pair = asParams[i].split("=");
	    if (pair.length == 2)
	    {
			if (pair[0].toLowerCase() == paramName)
		    {
				return pair[1];
		    }
	    }
    }

	return "";
}

//
// the currently selected node in the list control
var elmSelected = null;

// Message Archive Windows handling
//-- event handlers --
function OnMsgArchiveLoad() {
	//
	// document on load handler
	try
	{
		installEvents();
		initMessaging();
		lctrlInit();
	}
	catch(err)
	{
		noMessages();
	}
}

//
// assign javascript events to the list control
function installEvents()
{
	var elmListCtrl = document.getElementById("listctrl");
	if(elmListCtrl)
	{
		elmListCtrl.onkeydown = lctrlKeyUpDn;
	}
}

// 	<!-- scripting for dhtml management and page specifics -->

//
// Resizes the listbox and message snippet to the size of the first message snippet
function sizeControls(sizeWidth, sizeHeight) {
	sizeHeight_lc = Number(sizeHeight) + 2;
	document.getElementById("listctrl").style.width = sizeWidth + 'px';
	document.getElementById("listctrl").style.height = sizeHeight_lc + 'px';
	document.getElementById("snipframe").style.width = sizeWidth + 'px';
	document.getElementById("snipframe").style.height = sizeHeight + 'px';
}

//
// populate the list control with message titles
function lctrlInit()
{
	// populate the list control
	var sizeWidth = 0;
	var sizeHeight = 0;
	var elmMsgList = document.getElementById("msglist");
	var msgShown = 0;
	if(elmMsgList)
	{
		var elmDolly = document.getElementById("dolly");
		if(elmDolly)
		{
		    var nMessageCnt = aMessages.length;
			if(nMessageCnt > 0)
			{
				var strMsgTypeFilter = extractParam(""+document.location, "Category");
				var strMsgTypes = null;
				if (strMsgTypeFilter.length != 0)
				{
				    strMsgTypeFilter = strMsgTypeFilter.toLowerCase();
                    strMsgTypes = strMsgTypeFilter.split("|");
                }
                var strMsgIDListFilter = extractParam(""+document.location, "MsgIDList");
                var strMsgIDList = null;
				if (strMsgIDListFilter.length != 0)
				{
                    strMsgIDList = strMsgIDListFilter.split(",");
                }

				// for each message insert an item into the list control
				for( var itrMsg = 0 ; itrMsg < nMessageCnt ; itrMsg++ )
				{
					// we will not display the message in the case that a message filter has been applied
					// if the message type is not available we will assume it should be displayed

					var strMsgType = aMessages[itrMsg].strType.toLowerCase();
					var strMsgSubTypeLevel1 = aMessages[itrMsg].strSubTypeLevel1;
                    var strMsgID = aMessages[itrMsg].id;

					// display the message if there is no filter or the filter matches the type
					if( IsMessageTypeMatches(strMsgTypes, strMsgType, strMsgSubTypeLevel1, strMsgIDList,strMsgID ) )
					{
						if (sizeWidth < aMessages[itrMsg].strMessageWidth) {
						    sizeWidth = aMessages[itrMsg].strMessageWidth;
						}
						if (sizeHeight < aMessages[itrMsg].strMessageHeight) {
						    sizeHeight = aMessages[itrMsg].strMessageHeight;
						}
					
						var elmClone = elmDolly.cloneNode(true);
						if(elmClone)
						{
							elmClone.id = aMessages[itrMsg].id;
							elmClone.onclick = function(){lctrlSelectItem(this);};
							elmClone.className = "";
							elmClone.innerText = aMessages[itrMsg].strTitle;

							if(! aMessages[itrMsg].bViewed)
							{
								elmClone.style.fontWeight = "bold";
							}

							elmMsgList.appendChild(elmClone);
							msgShown += 1;
						}
					}
				}
                if (sizeHeight > 0 && sizeWidth > 0) {
                    sizeControls(sizeWidth, sizeHeight);
                }
			}
			if (msgShown == 0)
			{
				noMessages();
			}
		}
	}

	// place focus on the list control
	var elmLstCtrl = document.getElementById("listctrl");
	if(elmLstCtrl)
	{
		elmLstCtrl.focus();
	}

	// select the proper item in the list control
	lctrlSelectFirst();
}

// test if the message type is matching
function IsMessageTypeMatches(strMsgTypesFilter, strMsgType, strMsgSubTypeLevel1, strMsgIDList,strMsgID)
{             
    var bRet = false;
    
    if ( strMsgIDList != null && strMsgIDList.length > 0)
    {
        // had message id list filter
        var i =  0;
        for ( i = 0; i < strMsgIDList.length; i++)
        {
            if ( strMsgID == strMsgIDList[i])
            {
                bRet  = true;
                break;
            }
        }
    } 
    else if (strMsgTypesFilter != null && strMsgTypesFilter.length > 0)
    {
        var i =  0;
        for ( i = 0; i < strMsgTypesFilter.length; i++)
        {
            if ( strMsgType == strMsgTypesFilter[i])
            {
                bRet  = true;
                break;
            }
        }
    }
    else
    {
        // not Category or MsgIDList filter
        if ( strMsgType == "download")
        {
            bRet = true;
        }
        if ( strMsgType == "update")
        {
            bRet = true;
        }
        
        if ( strMsgSubTypeLevel1== null || strMsgSubTypeLevel1 == "")
        {
            bRet = true;
        }
    }
    return bRet;
}
//
// select the best element in the list control
function lctrlSelectFirst()
{
	var bSelectRequested = false;

	// try to select the requested item
	var strRequestedID = extractParam(""+document.location,"msgID");
	if(strRequestedID.length > 0)
	{
		var elmRequested = document.getElementById(strRequestedID);
		if(elmRequested)
		{
			lctrlSelectItem(elmRequested);
			bSelectRequested = true;
		}
	}

	// select the first item in the list
	if(! bSelectRequested)
	{
		var elmMsgList = document.getElementById("msglist");
		if(elmMsgList)
		{
			lctrlSelectItem(elmMsgList.firstChild);
		}
	}
}


//
// select a specific item in the list control
function lctrlSelectItem(elmToSelect)
{
	if(elmToSelect)
	{
		var elmMsgList = document.getElementById("msglist");
		if(elmMsgList)
		{
			for( var elmItr = 0 ; elmItr < elmMsgList.children.length ; elmItr++ )
			{
				elmMsgList.children[elmItr].className = "listunsel";
			}
			elmToSelect.className = "listsel";
			elmSelected = elmToSelect;
			if ((elmSelected != null) && (elmSelected.id != null) && (elmSelected.id.length > 0))
			{
				var elmIframe = document.getElementById("snipframe");
				if(elmIframe)
				{
					var contentURL = window.external.GetMessageLocalPath(elmSelected.id);
					elmIframe.src = window.external.QualifyRelativePath( contentURL );
				}
			}
		}
	}
}

//
// handle the keydown event for the list control
function lctrlKeyUpDn()
{
	var bRet = true;
	if(elmSelected)
	{
		switch(window.event.keyCode)
		{
			case 38:	/* up */
				lctrlSelectItem(elmSelected.previousSibling);
				bRet = false;
				break;
			case 40:	/* down */
				lctrlSelectItem(elmSelected.nextSibling);
				bRet = false;
				break;
		}
	}
	return bRet;
}

//
// insert an error message into the list control
function noMessages()
{
	var elmMsgList = document.getElementById("msglist");
	if(elmMsgList)
	{
		deleteNode(elmMsgList);

		var elmNoMessage = document.getElementById("nomessage");
		if(elmNoMessage)
		{
			var elmClone = elmNoMessage.cloneNode(true);
			if(elmClone)
			{
				elmClone.id = "";
				elmClone.className = "error";

				var elmLstCtrl = document.getElementById("listctrl");
				if(elmLstCtrl)
				{
					elmLstCtrl.appendChild(elmClone);
				}
			}
		}
	}
}

//
// properly delete a node from the DOM
function deleteNode(elmToDelete)
{
	if(elmToDelete)
	{
		deleteNode(elmToDelete.firstChild);
		elmToDelete.parentNode.removeChild(elmToDelete);
	}
}


//<!-- functions called by hosting app -->
// used by host app to notify the caller that the PCU action is complete
function ActionCompleted()
{}

//
// called by hosting app to determine which message is being shown
function GetCurrentMsgID()
{
	var strMsgID = "";

	if(null!= elmSelected)
	{
		strMsgID = elmSelected.id;
		elmSelected.style.fontWeight = "normal";
	}

	return strMsgID;
}

//
// called by hosting app to get detail URL
function GetCurrentMsgDetailURL()
{
	var strMsgDetail = "";

	if((null != elmSelected) && (null != aMessages))
	{
		for(var itrMsg = 0 ; itrMsg < aMessages.length ; itrMsg++)
		{
			if(elmSelected.id == aMessages[itrMsg].id)
			{
				strMsgDetail = window.external.QualifyRelativePath( aMessages[itrMsg].strDetail );
				break;
			}
		}
	}

	return strMsgDetail;
}
