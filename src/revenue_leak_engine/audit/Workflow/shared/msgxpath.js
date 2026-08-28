/* JS available to all messages */

//checks if user is online or offline
function isSystemOnline()
{
	var bIsOnline = false;
    try {
    	bIsOnline = window.external.IsXPathConditionValid('/systeminfo[@online="true"]');
	}
	catch(err) {
		bIsOnline = true;
	}
	return bIsOnline;
}

//evaluates an xpath condition for a message
function msgvisicheck(xpath)
{
	return window.external.IsXPathConditionValid(xpath);
}