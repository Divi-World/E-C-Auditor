// JScript source code

// parameter values used
var strTotalDays = "TotalDays";
var strUsedDays = "NumDays";

function reLayout(strURL)
{
	var nTrialTotal = 0;
	var bShowCounter = false;
	var strShow = extractParam(strURL, "ShowCounter");
	if(strShow.toLowerCase() == "yes") {
	    bShowCounter = true;
	}
	if (bShowCounter) {
		// get the values for the trial total
		var strTrialTotal = extractParam(strURL,strTotalDays);
		if(strTrialTotal.length  > 0) {
			nTrialTotal = parseInt(strTrialTotal,10);
		}
		if ( nTrialTotal <= 0) {
		    bShowCounter = false;
		}
	}
	//only do this if the counter is to be shown	
	if (bShowCounter)
	{
		var tdProgress = document.getElementById("tdProgress");
		if(tdProgress == null) {		
			tdProgress = window.parent.document.getElementById("tdProgress");
		}
		if (tdProgress != null) {
			tdProgress.style.display = "";
		}	
			
		// get the values for the trial remaining
		var strDaysRemain = extractParam(strURL,strUsedDays);
		var nDaysRemain = 0;
		if(strDaysRemain.length > 0) {
			nDaysRemain = parseInt(strDaysRemain,10);
		}
		if (nDaysRemain < 0) {
			nDaysRemain = 0;
		}
		
		//insert localized days left strings
		var langc = extractParam(strURL, "Lang");
		langc = langc.toLowerCase();
		var daysleftstr = 'Days Left';
		switch(langc) {
			case 'br':
				daysleftstr = 'Dias Restantes';
			break;
			case 'cs':
				daysleftstr = '剩余 天';
			break;
			case 'ct':
				daysleftstr = '天後到期';
			break;
			case 'cz':
				daysleftstr = 'Dní Zbývá';
			break;
			case 'de':
				daysleftstr = 'Verbleibende Tage';
			break;
			case 'es':
				daysleftstr = 'Días de prueba restantes';
			break;
			case 'fr':
				daysleftstr = 'Jours Restants';
			break;
			case 'it':
				daysleftstr = 'Giorni Rimasti';
			break;
			case 'jp':
				daysleftstr = '日間試用可能';
			break;
			case 'nl':
				daysleftstr = 'Dagen Over';
			break;
			case 'pl':
				daysleftstr = 'Pozostało Dni';
			break;
			case 'ru':
				daysleftstr = 'Дней Осталось';
			break;
			case 'sv':
				daysleftstr = 'Dagar Kvar';
			break;
			case 'tr':
				daysleftstr = 'Gün Kaldi';
			break;
			default:
				daysleftstr = 'Days Left';
		}
		var elmDaysLeftstr = document.getElementById("divDaysLeftOnBanner");
		if(elmDaysLeftstr == null) {		
			elmDaysLeftstr = window.parent.document.getElementById("divDaysLeftOnBanner");
		}
		if(null != elmDaysLeftstr) {
			elmDaysLeftstr.innerText = daysleftstr;
		}

		// insert the days remaining into the page
		var elmCounter = document.getElementById("divCountOnBanner");
		if(elmCounter == null) {		
			elmCounter = window.parent.document.getElementById("divCountOnBanner");
		}
		if(null != elmCounter) {
			elmCounter.innerText = String(nDaysRemain);
		}

		// adjust the size of the progress bar
		var elmUnderSlider = document.getElementById("divUnderSlider");
		if(elmUnderSlider == null) {		
			elmUnderSlider = window.parent.document.getElementById("divUnderSlider");
		}
		var elmOverSlider = document.getElementById("divOverSlider");
		if(elmOverSlider == null) {		
			elmOverSlider = window.parent.document.getElementById("divOverSlider");
		}
		if(null != elmOverSlider && null != elmUnderSlider)
		{
			// get the days remaining as a percentage
			var nPercent = (nDaysRemain / nTrialTotal);
			if(nPercent > 1)
			{
				nPercent = 1;
			}
			
			// get the total length of the progress bar and compute the desired length of the slider
			var nTotalWidth = parseInt(elmUnderSlider.offsetWidth);
			var nPartWidth = (nTotalWidth * nPercent);
			if ( nPartWidth < nTotalWidth ) {
				elmOverSlider.style.width = String(nPartWidth) + 'px';
			}
		}
	}
	else
	{
		// hide progressbar
		var tdProgress = document.getElementById("tdProgress");
		if(tdProgress == null) {		
			tdProgress = window.parent.document.getElementById("tdProgress");
		}
		if (tdProgress != null) {
			tdProgress.style.display = "none";
		}	
	}
	
	// Hide regSection
	var strURLlow = strURL.toLowerCase();
	var regType = extractParam(strURLlow, "regtype");
	var registered = extractParam(strURLlow, "isregistered");		
	var nStatus = extractParam(strURLlow, "status");
	var regSection = document.getElementById("regSection");
	if ( regSection != null )
	{
		var bHide = true;
		if ( regType != null && regType == "2" && registered != null && registered != "1" )
		{
			if (nStatus != null && nStatus != '3')
			{
				bHide = false;
			}	
		}
		
		if (bHide)
		{
			regSection.style.visibility = "hidden";
		}
		else
		{
			regSection.style.visibility = "visible";
		}	
	}
}

function ShowBanner(strShow)
{
	var banner = document.getElementById("banner");
	if (banner != null) 
	{
		if ( strShow.toLowerCase() == "no" )
		{
			banner.style.display = "none";
		}
		else 
		{
			banner.style.display = "inline";
		}
	}
}

function SetActivationCodeElement()
{
	var strActCode = getParamVal("activationcode");
	var oTxt = document.getElementById("txtActivationCode");
	
	if (strActCode != null && oTxt != null)
		oTxt.value = strActCode.toUpperCase();
}

function getParamString()
{
  var sParamString = "";
	var sQueryVar = location.search;
	var nIndex = sQueryVar.indexOf("?");
	if ( nIndex >= 0 )
	{
	  sParamString = sQueryVar.substr(nIndex);
  }	
  
  return sParamString;
}

function getParamVal(paramName)
{
	var sQueryVar = location.search.toLowerCase();
	sQueryVar = unescape(sQueryVar);
	return extractParam(sQueryVar, paramName);
}	

function extractParam(sQueryVar, paramName)
{
	if (sQueryVar == null || paramName == null)
	  return "";

	var nIndex = sQueryVar.indexOf("?");
	if (nIndex >= 0)
		sQueryVar = sQueryVar.substr(nIndex + 1);

	paramName = paramName.toLowerCase();

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



function getParamValCaseSentitive(paramName)
{
	var sQueryVar = location.search;
	sQueryVar = unescape(sQueryVar);
	return extractParam(sQueryVar, paramName);
}


function EnableContinue(bEnable)
{
	var oBtn = document.getElementById("pcubtncontinue");
	if (oBtn != null)
	{
		oBtn.disabled = (bEnable == false);
	}
}

function ExpandRelativeURL(sPage)
{
	var sPath = location.pathname;
	var lastbkslsh = sPath.lastIndexOf("\\");
	if (lastbkslsh < 0)
	{
		lastbkslsh = sPath.lastIndexOf("/");
	}
	if (lastbkslsh < 0)
	{
		lastbkslsh = 0;
	}
	sPath = sPath.substr(0, lastbkslsh + 1);
	var sReturn = location.protocol + "//" + location.host + sPath + sPage;
	return sReturn;
}

function ValidateSerial(sSerial)
{
	if (sSerial != null && sSerial.match(/^\s*[a-zA-Z0-9]{2}\d{2}[a-zA-Z]{1}[a-zA-Z0-9]{2}-?[a-zA-Z0-9]{7}-?[a-zA-Z0-9]{7}-?[a-zA-Z0-9]{7}(?:\-?[a-zA-Z0-9]{5})?\s*$/) != null)
	{
		return true;
	}
	return false;
}

function ValidateActCode(sCode)
{
	if (sCode != null && sCode.match(/^\s*(?:[a-fA-F0-9]{4}-?){5}\s*$/) != null)
	{
		return true;
	}
	
	return false;
}

function FormatSerial(sCode)
{
	if (sCode != null && sCode.length >= 17 && sCode.indexOf("-") == -1)
	{
		var sNewCode = sCode.substr(0,7) + "-" + sCode.substr(7,7) + "-" + sCode.substr(14);
		sNewCode = sNewCode.toUpperCase();
		return sNewCode;
	}
	else
	{
		return sCode;
	}
}

function FormatActivationCode(sCode)
{
	if (sCode != null && sCode.length == 20 && sCode.indexOf("-") == -1)
	{
		var sNewCode = sCode.substr(0,4) + "-" + sCode.substr(4,4) + "-" + 
									 sCode.substr(8,4) + "-" + sCode.substr(12,4) + "-" + sCode.substr(16,4);
		sNewCode = sNewCode.toUpperCase();
		return sNewCode;
	}
	else
	{
		return sCode;
	}
}


function regChangeLaunchButtonTitle()
{
	var btnClose = document.getElementById("btnClose");
	if ( btnClose != null )
	{
		btnClose.style.display = "inline";
		
		var btnLaunch = document.getElementById("btnLaunch");
		if ( btnLaunch != null )
		{
			btnLaunch.style.display = "none";
		}
	}
}

function OnUnlock()
{
	location='pcucmd://Unlock?admin=yes'; 
	location='pcucmd://Next?condition=true'			
}

// Flash Player Version Detection - Rev 1.6
// Detect Client Browser type
// Copyright(c) 2005-2006 Adobe Macromedia Software, LLC. All rights reserved.
var isIE  = (navigator.appVersion.indexOf("MSIE") != -1) ? true : false;
var isWin = (navigator.appVersion.toLowerCase().indexOf("win") != -1) ? true : false;
var isOpera = (navigator.userAgent.indexOf("Opera") != -1) ? true : false;

function ControlVersion()
{
	var version;
	var axo;
	var e;

	// NOTE : new ActiveXObject(strFoo) throws an exception if strFoo isn't in the registry

	try {
		// version will be set for 7.X or greater players
		axo = new ActiveXObject("ShockwaveFlash.ShockwaveFlash.7");
		version = axo.GetVariable("$version");
	} catch (e) {
	}

	if (!version)
	{
		try {
			// version will be set for 6.X players only
			axo = new ActiveXObject("ShockwaveFlash.ShockwaveFlash.6");

			// installed player is some revision of 6.0
			// GetVariable("$version") crashes for versions 6.0.22 through 6.0.29,
			// so we have to be careful.

			// default to the first public version
			version = "WIN 6,0,21,0";

			// throws if AllowScripAccess does not exist (introduced in 6.0r47)
			axo.AllowScriptAccess = "always";

			// safe to call for 6.0r47 or greater
			version = axo.GetVariable("$version");

		} catch (e) {
		}
	}

	if (!version)
	{
		try {
			// version will be set for 4.X or 5.X player
			axo = new ActiveXObject("ShockwaveFlash.ShockwaveFlash.3");
			version = axo.GetVariable("$version");
		} catch (e) {
		}
	}

	if (!version)
	{
		try {
			// version will be set for 3.X player
			axo = new ActiveXObject("ShockwaveFlash.ShockwaveFlash.3");
			version = "WIN 3,0,18,0";
		} catch (e) {
		}
	}

	if (!version)
	{
		try {
			// version will be set for 2.X player
			axo = new ActiveXObject("ShockwaveFlash.ShockwaveFlash");
			version = "WIN 2,0,0,11";
		} catch (e) {
			version = -1;
		}
	}

	return version;
}

// JavaScript helper required to detect Flash Player PlugIn version information
function GetSwfVer(){
	// NS/Opera version >= 3 check for Flash plugin in plugin array
	var flashVer = -1;

	if (navigator.plugins != null && navigator.plugins.length > 0) {
		if (navigator.plugins["Shockwave Flash 2.0"] || navigator.plugins["Shockwave Flash"]) {
			var swVer2 = navigator.plugins["Shockwave Flash 2.0"] ? " 2.0" : "";
			var flashDescription = navigator.plugins["Shockwave Flash" + swVer2].description;
			var descArray = flashDescription.split(" ");
			var tempArrayMajor = descArray[2].split(".");
			var versionMajor = tempArrayMajor[0];
			var versionMinor = tempArrayMajor[1];
			var versionRevision = descArray[3];
			if (versionRevision == "") {
				versionRevision = descArray[4];
			}
			if (versionRevision[0] == "d") {
				versionRevision = versionRevision.substring(1);
			} else if (versionRevision[0] == "r") {
				versionRevision = versionRevision.substring(1);
				if (versionRevision.indexOf("d") > 0) {
					versionRevision = versionRevision.substring(0, versionRevision.indexOf("d"));
				}
			}
			var flashVer = versionMajor + "." + versionMinor + "." + versionRevision;
		}
	}
	// MSN/WebTV 2.6 supports Flash 4
	else if (navigator.userAgent.toLowerCase().indexOf("webtv/2.6") != -1) flashVer = 4;
	// WebTV 2.5 supports Flash 3
	else if (navigator.userAgent.toLowerCase().indexOf("webtv/2.5") != -1) flashVer = 3;
	// older WebTV supports Flash 2
	else if (navigator.userAgent.toLowerCase().indexOf("webtv") != -1) flashVer = 2;
	else if ( isIE && isWin && !isOpera ) {
		flashVer = ControlVersion();
	}
	return flashVer;
}

// When called with reqMajorVer, reqMinorVer, reqRevision returns true if that version or greater is available
function DetectFlashVer(reqMajorVer, reqMinorVer, reqRevision)
{
	versionStr = GetSwfVer();
	if (versionStr == -1 ) {
		return false;
	} else if (versionStr != 0) {
		if(isIE && isWin && !isOpera) {
			// Given "WIN 2,0,0,11"
			tempArray         = versionStr.split(" "); 	// ["WIN", "2,0,0,11"]
			tempString        = tempArray[1];			// "2,0,0,11"
			versionArray      = tempString.split(",");	// ['2', '0', '0', '11']
		} else {
			versionArray      = versionStr.split(".");
		}
		var versionMajor      = versionArray[0];
		var versionMinor      = versionArray[1];
		var versionRevision   = versionArray[2];

        	// is the major.revision >= requested major.revision AND the minor version >= requested minor
		if (versionMajor > parseFloat(reqMajorVer)) {
			return true;
		} else if (versionMajor == parseFloat(reqMajorVer)) {
			if (versionMinor > parseFloat(reqMinorVer))
				return true;
			else if (versionMinor == parseFloat(reqMinorVer)) {
				if (versionRevision >= parseFloat(reqRevision))
					return true;
			}
		}
		return false;
	}
}

function AC_AddExtension(src, ext)
{
  if (src.indexOf('?') != -1)
    return src.replace(/\?/, ext+'?');
  else
    return src + ext;
}

function AC_Generateobj(objAttrs, params, embedAttrs)
{
    var str = '';
    if (isIE && isWin && !isOpera)
    {
  		str += '<object ';
  		for (var i in objAttrs)
  			str += i + '="' + objAttrs[i] + '" ';
  		for (var i in params)
  			str += '><param name="' + i + '" value="' + params[i] + '" /> ';
  		str += '></object>';
    } else {
  		str += '<embed ';
  		for (var i in embedAttrs)
  			str += i + '="' + embedAttrs[i] + '" ';
  		str += '> </embed>';
    }

    document.write(str);
}

function AC_FL_RunContent(){
  var ret =
    AC_GetArgs
    (  arguments, ".swf", "movie", "clsid:d27cdb6e-ae6d-11cf-96b8-444553540000"
     , "application/x-shockwave-flash"
    );
  AC_Generateobj(ret.objAttrs, ret.params, ret.embedAttrs);
}

function AC_GetArgs(args, ext, srcParamName, classid, mimeType){
  var ret = new Object();
  ret.embedAttrs = new Object();
  ret.params = new Object();
  ret.objAttrs = new Object();
  for (var i=0; i < args.length; i=i+2){
    var currArg = args[i].toLowerCase();

    switch (currArg){
      case "classid":
        break;
      case "pluginspage":
        ret.embedAttrs[args[i]] = args[i+1];
        break;
      case "src":
      case "movie":
        args[i+1] = AC_AddExtension(args[i+1], ext);
        ret.embedAttrs["src"] = args[i+1];
        ret.params[srcParamName] = args[i+1];
        break;
      case "onafterupdate":
      case "onbeforeupdate":
      case "onblur":
      case "oncellchange":
      case "onclick":
      case "ondblClick":
      case "ondrag":
      case "ondragend":
      case "ondragenter":
      case "ondragleave":
      case "ondragover":
      case "ondrop":
      case "onfinish":
      case "onfocus":
      case "onhelp":
      case "onmousedown":
      case "onmouseup":
      case "onmouseover":
      case "onmousemove":
      case "onmouseout":
      case "onkeypress":
      case "onkeydown":
      case "onkeyup":
      case "onload":
      case "onlosecapture":
      case "onpropertychange":
      case "onreadystatechange":
      case "onrowsdelete":
      case "onrowenter":
      case "onrowexit":
      case "onrowsinserted":
      case "onstart":
      case "onscroll":
      case "onbeforeeditfocus":
      case "onactivate":
      case "onbeforedeactivate":
      case "ondeactivate":
      case "type":
      case "codebase":
        ret.objAttrs[args[i]] = args[i+1];
        break;
      case "id":
      case "width":
      case "height":
      case "align":
      case "vspace":
      case "hspace":
      case "class":
      case "title":
      case "accesskey":
      case "name":
      case "tabindex":
        ret.embedAttrs[args[i]] = ret.objAttrs[args[i]] = args[i+1];
        break;
      default:
        ret.embedAttrs[args[i]] = ret.params[args[i]] = args[i+1];
    }
  }
  ret.objAttrs["classid"] = classid;
  if (mimeType) ret.embedAttrs["type"] = mimeType;
  return ret;
}

/* function used for tab switching */

function switchtabs(id,exc,max)
{
	//exception where 'exc' tab doesnt show bottom table
	if (exc > 0)
	{
		var bottomtable = document.getElementById('bottomtable');
		
		if (id == exc) {
			bottomtable.style.display = 'none';
		}
		else {
			bottomtable.style.display = '';
		}
	}

	for(var i=1;i<=max;i++)
	{
		var tabcontent = document.getElementById('tabpage' + i);
		var tabitem = document.getElementById('tab' + i);

		//change tab content
		if (i!=id) {
			tabcontent.style.display = 'none';
		}
		else {
			tabcontent.style.display = '';
		}

		//highlight tab
		if (i!=id) {
			tabitem.style.backgroundColor = 'black';
			tabitem.childNodes[0].style.color = 'white';
		}
		else {
			tabitem.style.backgroundColor = 'white';
			tabitem.childNodes[0].style.color = 'black';
		}
	}
}

/* function used for opening up a URL or predefined content in a pop-up window */

function popitup(url,height,width)
{	
	var dimensions = "height=" + height + ",width=" + width + "'";

	//generate new window with a unique name everytime someone clicks
	var uniqid = Math.floor(Math.random()*100001);
	newwindow = window.open(url,'popup' + uniqid,dimensions);

	//popups with predefined content
	if (url == 'about:blank')
	{
		if (arguments[3] == 'MB') {
			newwindow.document.body.innerHTML = '<h2 style="font-size: 14px">Corel 30-Day Money-Back Guarantee</h2><div>At Corel, we\'re proud of our products and we\'re confident that you\'ll be satisfied with your purchase. That\'s why we offer the <strong>Corel 30-Day Money-Back Guarantee</strong>. Buy today and if you\'re not completely satisfied with your purchase, Corel will refund your money based on your original method of payment &#151; excluding any shipping costs. When you contact us about a return, your Corel Customer Service Representative may inquire as to the reason for your return so we can improve our products and our customer experience.</div><div style="margin-top: 10px"><strong>Please note</strong>: Only products purchased directly from Corel qualify for the Corel 30-Day Money-Back Guarantee. Purchases made from a retailer must be returned to where you made your purchase and are subject to the return policy of that retailer. Purchases of transactional license, maintenance purchases, Wilcom DecoStudio products, Wacom Cintiq products and download insurance are excluded from the 30 day money back guarantee.</div>';
		}
		else if (arguments[3] == 'UPGRADE') {
			newwindow.document.body.innerHTML = '<h2 style="font-size: 14px">Here\'s how you qualify to save big!</h2><div>If you own any of the following products, you can get Corel Paint Shop Pro Photo X2 Ultimate for only $59.99:</div><ul><li>Microsoft&reg; Digital Image Pro, Digital Image Suite or Picture It</li><li>Ulead&reg;/Nova&reg; Photo Impact or Nova&reg; Photo Explosion</li><li>CorelDRAW&reg;, CorelDRAW&reg; Graphics Suite, Corel&reg; Painter or Corel&reg; Painter Essentials</li></ul><div style="font-weight: bold">Get upgrade savings and order Paint Shop Pro Photo X2 Ultimate today!</div>';
		}
		else {
			newwindow.document.body.innerHTML = arguments[3];
		}
	}
	newwindow.focus();
}

function setCookie(name, value) 
{
    var newCookie = name + "=" + escape(value) + "; path=/";
    document.cookie = newCookie;
}

function getCookie(name) 
{
    var prefix = name + "="
    var cookieStartIndex = document.cookie.indexOf(prefix)
    if (cookieStartIndex == -1)
        return null
    var cookieEndIndex = document.cookie.indexOf(";", cookieStartIndex + prefix.length)
    if (cookieEndIndex == -1)
        cookieEndIndex = document.cookie.length
    return unescape(document.cookie.substring(cookieStartIndex + prefix.length, cookieEndIndex))
}

function deleteCookie(name) 
{
    if (getCookie(name)) 
    {
        document.cookie = name + "=; path=/; expires=Thu, 01-Jan-70 00:00:01 GMT";
    }
}

function removeAllSpaces(strVal)
{
    return strVal.replace(/\s/g,"");
}

function init_trial_page()
{
	try {
		location.href = "pcucmd://SetCookie?lusr=''";
		setCookie("lusr","");
		SetExtensionPeriodText();
		headInit();
	}
	catch(e) {};
}

function SetExtensionPeriodText()
{
	var extensionPeriodElmentList = document.getElementsByName("ExtensionPeriodText");
	if ( extensionPeriodElmentList != null && extensionPeriodElmentList.length > 0)
	{
		var extensionPeriodDays = getParamVal("ExtensionPeriod");
		if ( extensionPeriodDays!= null)
		{
			var extensionPeriodElment = null;
			var i = 0;
			for ( i = 0; i < extensionPeriodElmentList.length; i++)
			{
				extensionPeriodElment = extensionPeriodElmentList[i];
				if ( extensionPeriodElment != null)
				{
					extensionPeriodElment.innerText = extensionPeriodDays;
				}
			}
		}
	}
}

/* the caller to the below 2 functions has to implement the callback functions calBack(strReturn) which will be called upon completion of the async call */
function sendEmailValidation() {
    var xmlhttp;
    var strURL = "http://iws.corel.com/ipmws/sendEmailValidation" + getParamString();
    if (window.XMLHttpRequest) {
        // for IE7 and higher
        xmlhttp = new XMLHttpRequest();
    }
    else {
        // for IE6
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange = function () {
        var strReturn = "";
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                strReturn = xmlhttp.responseText;
                var token = "<body>";
                var tokenIndex = strReturn.indexOf(token);
                if (tokenIndex > -1) {
                    strReturn = strReturn.substring(tokenIndex + token.length);
                    token = "</body>";
                    tokenIndex = strReturn.indexOf(token);
                    if (tokenIndex > -1) {
                        strReturn = removeAllSpaces(strReturn.substring(0, tokenIndex));
						if (typeof callBack === "function") {
							callBack(strReturn);
						}
                    }
                }
            }
            else {
				if (typeof callBack === "function") {
					callBack("1");    //failed to send/connect
				}
            }
        }
    }
    xmlhttp.open("GET", strURL, true);
    xmlhttp.send();
}
function sendPremTrialStart() {
    var xmlhttp;
	var strURL = "https://iws.corel.com/ipmws/redirect/index.jsp" + getParamString();
    if (window.XMLHttpRequest) {
        // for IE7 and higher
        xmlhttp = new XMLHttpRequest();
    }
    else {
        // for IE6
        xmlhttp = new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange = function () {
        var strReturn = "";
        if (xmlhttp.readyState == 4) {
            if (xmlhttp.status == 200) {
                strReturn = xmlhttp.responseText;
                var token = "<body>";
                var tokenIndex = strReturn.indexOf(token);
                if (tokenIndex > -1) {
                    strReturn = strReturn.substring(tokenIndex + token.length);
                    token = "</body>";
                    tokenIndex = strReturn.indexOf(token);
                    if (tokenIndex > -1) {
                        strReturn = removeAllSpaces(strReturn.substring(0, tokenIndex));
                        callBack(strReturn);
                    }
                }
            }
            else {
                callBack("1");    //failed to send/connect
            }
        }
    }
    xmlhttp.open("GET", strURL, true);
    xmlhttp.send();
}

function changeEmail() {
    location = "pcucmd://fullbrowse?url='https://account.corel.com/accounts/user/accountEditEmail'";
}

/* form label functions */
function fieldin(fieldobj) {
	fieldobj.style.backgroundColor = '#fcfcfc';
}

function fieldout(fieldobj)
{
	if(fieldobj.value == '') {
		fieldobj.style.backgroundColor = 'transparent';
	}
}
/* end form label functions */

function getCorelComServer()
{
	var s = getParamVal("CorelComServer");
	if (s == '') {
		s = "http://www.corel.com/";
	}
	return s;
}

function launchStoreEx(noAdmin, fullBrowser, w, h) {
	var storeUrl = addGoogleAnalyticsParamsToUrl("http://apps.corel.com/redirect?_redirect=pcupurchase" + getPCUNVPs(true, noAdmin));
	var url = "pcucmd://browse?URL='" + storeUrl + "'&width=" + w + "&height=" + h;
	if(fullBrowser == "true" || fullBrowser == true){
			url = "pcucmd://fullbrowse?url='" + storeUrl + "'";
	}
	document.location.href = url;
}

// start moving window
function StartMoveWindow() {
   location='pcucmd://StartRCMoveWindow/';
}

//check if page inside iframe is on a different domain
function canAccessIframe(iframe) {
	try {
		var doc = iframe.contentWindow.document;
    }
	catch(err){
      return false;
    }
	return true;
}

//close container dialog
function CloseDlg() {
    //check if there is a content iframe
    var ifrm = document.getElementById("Content");
    if (ifrm != null) {
		//check if the content iframe document can be accessed
		if (canAccessIframe(ifrm) == true) {
			//check if content iframe has a cancel button with a custom message
			var cancelbtn = ifrm.contentWindow.document.getElementById("pcubtncancel");
			if (cancelbtn != null && cancelbtn.onclick) {
				cancelbtn.onclick({ target: cancelbtn });
			}
			else {
				document.location = 'pcucmd://cancel';
			}
		}
		else {
			document.location='pcucmd://cancel';
		}
    }
	else {
		document.location='pcucmd://cancel';
	}
}

//onclick forgot password
function forgotPassword() {
	location.href = "pcucmd://Connect";
	location.href = "pcucmd://setsequence?name=forgot_password&condition=true";
}

function supportlink() {
	location.href = "pcucmd://fullbrowse?url='<CorelComServer>/membersupport'";
	return false;
}

////////////////////////////////////////////////////////////////////////////////////////////
//
// Hash generator Interface
//
////////////////////////////////////////////////////////////////////////////////////////////

(function(sha256Generator) {
    // some utils used in calculating hash
    var sha256Utils = {};
    sha256Utils.ROTR = function(n, x) {
        return (x >>> n) | (x << (32 - n));
    };

    sha256Utils.S0 = function(x) {
        return sha256Utils.ROTR(2, x) ^ sha256Utils.ROTR(13, x) ^ sha256Utils.ROTR(22, x);
    };

    sha256Utils.S1 = function(x) {
        return sha256Utils.ROTR(6, x) ^ sha256Utils.ROTR(11, x) ^ sha256Utils.ROTR(25, x);
    };

    sha256Utils.s0 = function(x) {
        return sha256Utils.ROTR(7, x) ^ sha256Utils.ROTR(18, x) ^ (x>>>3);
    };

    sha256Utils.s1 = function(x) {
        return sha256Utils.ROTR(17, x) ^ sha256Utils.ROTR(19, x) ^ (x>>>10);
    };

    sha256Utils.Ch = function(x, y, z) {
        return (x & y) ^ (~x & z);
    };

    sha256Utils.Maj = function(x, y, z) {
        return (x & y) ^ (x & z) ^ (y & z);
    };

    sha256Utils.toHexStr = function(n) {
        var s = "", v;
        for(var i = 7; i >= 0; i--) {
            v = (n >>> (i * 4)) & 0xf; s += v.toString(16);
        }
        return s;
    };

    ////////////////////////////////////////////////////////////////////////////////////////////
    //
    // extend utf8Encode & utf8Decode function for String instance
    //
    ////////////////////////////////////////////////////////////////////////////////////////////
    if(typeof String.prototype.utf8Encode == 'undefined') {
        String.prototype.utf8Encode = function() {
            return unescape(encodeURIComponent(this));
        };
    }

    if(typeof String.prototype.utf8Decode == 'undefined') {
        String.prototype.utf8Decode = function() {
            try {
                return decodeURIComponent(escape(this));
            } catch (e) {
                return this;
            }
        };
    }
    
    ////////////////////////////////////////////////////////////////////////////////////////////
    //
    // impl of converting string to sha256 hash string
    //
    ////////////////////////////////////////////////////////////////////////////////////////////
    sha256Generator.hash = function(inputString) {
        inputString = inputString.toLowerCase();
        // Round constants: first 32 bits of the fractional parts of the cube roots of the first 64 primes
        var K = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        ];
        // Initial hash value: first 32 bits of the fractional parts of the square roots of the first 8 primes
        var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];

        inputString = inputString.utf8Encode();
        inputString += String.fromCharCode(0x80);
        var l = inputString.length / 4 + 2;
        var N = Math.ceil(l / 16);
        var M = new Array(N);
        for(var i = 0; i < N; i++) {
            M[i] = new Array(16);
            for(var j = 0; j < 16; j++) {
                M[i][j] = (inputString.charCodeAt(i * 64 + j * 4) << 24) | (inputString.charCodeAt(i * 64 + j * 4 + 1) << 16) | (inputString.charCodeAt(i * 64 + j * 4 + 2) << 8) | (inputString.charCodeAt(i * 64 + j * 4 + 3));
            }
        }
        M[N - 1][14] = ((inputString.length - 1) * 8) / Math.pow(2, 32); M[N - 1][14] = Math.floor(M[N - 1][14]);
        M[N - 1][15] = ((inputString.length - 1) * 8) & 0xffffffff;
        var W = new Array(64);
        var a, b, c, d, e, f, g, h;
        for(var i = 0; i < N; i++) {
            for(var t = 0;  t < 16; t++) {
                W[t] = M[i][t];
            }

            for(var t = 16; t < 64; t++) {
                W[t] = (sha256Utils.s1(W[t - 2]) + W[t - 7] + sha256Utils.s0(W[t - 15]) + W[t - 16]) & 0xffffffff;
            }
            
            a = H[0]; b = H[1]; c = H[2]; d = H[3]; e = H[4]; f = H[5]; g = H[6]; h = H[7];
            for(var t = 0; t < 64; t++) {
                var T1 = h + sha256Utils.S1(e) + sha256Utils.Ch(e, f, g) + K[t] + W[t];
                var T2 = sha256Utils.S0(a) + sha256Utils.Maj(a, b, c);
                h = g;
                g = f;
                f = e;
                e = (d + T1) & 0xffffffff;
                d = c;
                c = b;
                b = a;
                a = (T1 + T2) & 0xffffffff;
            }
            H[0] = (H[0] + a) & 0xffffffff;
            H[1] = (H[1] + b) & 0xffffffff;
            H[2] = (H[2] + c) & 0xffffffff;
            H[3] = (H[3] + d) & 0xffffffff;
            H[4] = (H[4] + e) & 0xffffffff;
            H[5] = (H[5] + f) & 0xffffffff;
            H[6] = (H[6] + g) & 0xffffffff;
            H[7] = (H[7] + h) & 0xffffffff;
        }

        return sha256Utils.toHexStr(H[0]) + sha256Utils.toHexStr(H[1]) + sha256Utils.toHexStr(H[2]) + sha256Utils.toHexStr(H[3]) + sha256Utils.toHexStr(H[4]) + sha256Utils.toHexStr(H[5]) + sha256Utils.toHexStr(H[6]) + sha256Utils.toHexStr(H[7]);
    }
}(window.sha256Generator = window.sha256Generator || {}));

//GA functions
function addOrUpdateQStringParam(a, e, r) {
    var n = new RegExp("([?&])" + e + "=.*?(&|$)", "i"),
        t = -1 !== a.indexOf("?") ? "&" : "?";
    return a.match(n) ? a.replace(n, "$1" + e + "=" + r + "$2") : a + t + e + "=" + r
}

function addGoogleAnalyticsParamsToUrl(url, term, msgid)
{
	originalUrl = url;
	try
	{
		url = addOrUpdateQStringParam(url, "utm_term", term);
		url = addOrUpdateQStringParam(url, "ctm_term", term);
		url = addOrUpdateQStringParam(url, "utm_medium","IPM");
		url = addOrUpdateQStringParam(url, "ctm_medium","IPM");
		url = addOrUpdateQStringParam(url, "utm_source","<License>-<SourceID>");
		url = addOrUpdateQStringParam(url, "ctm_source","<License>-<SourceID>");
		url = addOrUpdateQStringParam(url, "utm_campaign", msgid);
		url = addOrUpdateQStringParam(url, "ctm_campaign", msgid);
		url = addOrUpdateQStringParam(url, "utm_content", "<PCID>");
		url = addOrUpdateQStringParam(url, "ctm_content", "<PCID>");
		url = addOrUpdateQStringParam(url, "x-vehicle", term);
		g_resolvedURL = url;
		location = "pcucmd://replacetoken?addtrack=false&callback='rptCallback'&string=\'" + url + "\'";
		url = g_resolvedURL
		var lidsid = window.location.pathname;
		var lidsidpos = lidsid.indexOf("/Corel/Messages/");
		if (lidsidpos != -1) {
			lidsidpos = lidsidpos + 16;
			lidsid = lidsid.substring(lidsidpos, lidsidpos + 16);
			url = url.replace(/<License>-<SourceID>/gi, lidsid);
		}
	}
	catch (err) {
		url = originalUrl;
		var lidsid = window.location.pathname;
		var lidsidpos = lidsid.indexOf("/Corel/Messages/");
		if (lidsidpos != -1) {
			lidsidpos = lidsidpos + 16;
			lidsid = lidsid.substring(lidsidpos, lidsidpos + 16);
			url = url.replace(/<License>-<SourceID>/gi, lidsid);
		}
	}
	
    return url;
}