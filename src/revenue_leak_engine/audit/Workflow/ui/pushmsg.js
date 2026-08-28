//
// Global variables - republished
//
var gMessageID = "";
var fTestingMode = false;

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

function OnConnect() {
	location = "pcucmd://Connect?showerror='no'";
	location = "pcucmd://Cancel?confirm=no&condition=false";
}

//
// onLoad - called when the document is fully loaded
//
function onLoad()
{
	window.onerror = handleError;

	// If testing is enabled, show testing aids
	//var testing = getParamVal("testing");
	//if (testing)
	fTestingMode = false;

	var dnd=getParamVal("dnd");
    var tdDNDDiv=document.getElementById("dnd");
    if (tdDNDDiv != null)
    {
        if (dnd=="1")
        {
            tdDNDDiv.style.display = "";
        }
        else
        {
            tdDNDDiv.style.display = "none";
        }
    }

	// Previewing a message with a given ID?
	var msgID = getParamVal("msgid");
	if ( msgID )
	{
	    gMessageID = msgID;
		showAMessage(msgID);
	}
}

//
// Function to handle all error
//
function handleError(sMsg, sUrl, sLine)
{
	// If we are not in testing mode, supress error dialogs
	if ( !fTestingMode )
		return true;

	// Display a detaled error message
	var sErrMsg = "Error occured!<br/>";
	sErrMsg += "Error: " + sMsg + "<br/>";
	sErrMsg += "at: " + sUrl + "<br/>";
	sErrMsg += "Line: " + sLine + "<br/>";
	sErrMsg += "<br/>";
	sErrMsg += "<br /><a href='#' onclick='onCloseInfo()'>Close</a>"

	msgInfo.innerHTML = sErrMsg;
	msgInfo.style.display = "inline";

	return true;
}

//
// showAMessage - Shows a single message without transitions or rotation
//
function showAMessage(msgID)
{
		// Get the message body URL
		var dsptype = getParamVal("dsptype");
		var contentURL = "";
		if ((dsptype != null) && (dsptype == "popup"))
		{
			var oCurrentMessageXMLNode = window.external.GetMessage(msgID);
			var contentObj = oCurrentMessageXMLNode.selectSingleNode("contents/content[@type='detail']/@localpath");
			if (contentObj != null) {
			    contentURL = contentObj.text;
			}
			else {
			    contentURL = window.external.GetMessageLocalPath(msgID);
			}
		}
		else
		{
			contentURL = window.external.GetMessageLocalPath(msgID);
		}


		// Show the new message
		var FullURLPath = window.external.QualifyRelativePath(contentURL);

		document.all.messageBody.src = FullURLPath;

		var strwidth = getParamVal("width") + 'px';
		var strheight = getParamVal("height") + 'px';
		document.all.messageBody.style.width = strwidth;
		document.all.messageBody.style.height = strheight;
	    window.external.NotifyMessageTracking( msgID, "Push", "View" );
}

// gets called by app
// returns the Message ID to the app
function GetCurrentMsgID()
{
    return gMessageID;
}

//
// onMouseOverBody - Called when the mouse hovers over tht message body
//
function onMouseOverBody()
{
	// Don't bother if testing mode is not enabled
	// ie., no "testing=1" in the URL param
	if ( !fTestingMode )
		return;

	// Show the testing aid
	var testingAidElem = document.getElementById("testingAid");
	if ( testingAidElem != null )
		testingAidElem.style.display = "inline";
}

function GetCurrentMsgDetailURL()
{
    var url = "";
    var FullURLPath = "";
    var msgID = GetCurrentMsgID();
	var objMessage = window.external.GetMessage(msgID);
    var msgDetailURLNode = objMessage.selectSingleNode("contents/content[@type='detail']/@localpath");
    if ( msgDetailURLNode != null )
    {
        url = msgDetailURLNode.value;
        FullURLPath = window.external.QualifyRelativePath(url);
    }

    return FullURLPath;
}

//
// onMouseOutOfBody - Called when mouse is out of message body
//
function onMouseOutOfBody()
{
	if ( !fTestingMode )
		return;

	// Hide testing aid
	testingAid.style.display = "none";
}

//
// onCloseInfo - Called to close the msg info window
//
function onClose()
{
    location="pcucmd://continue?addtrack=no";
}

function onUnload()
{
	var dontDisplay = document.getElementById("dontdisplay");
	if (dontDisplay != null)
	{
	    if (dontDisplay.checked)
	    {
	        window.external.MessageDoNotDisplay(gMessageID);
	    }
	}
}

function reslidsid(str) {
	document.getElementById('restoken_lidsid').innerHTML = str;
}

