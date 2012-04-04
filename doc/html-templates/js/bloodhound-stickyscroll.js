	$(document).ready(function stickyStatus() {
	$(window).scroll(function onScroll() {
	
    var docViewTop = $(window).scrollTop();
    var docViewBottom = docViewTop + $(window).height();

    var elemTop = $("header").offset().top;
    var elemBottom = elemTop + $("header").height();
    
	if (docViewTop > elemBottom) {
		$("#stickyactivity").attr("style", "position: fixed; top: 0;")
		$("#stickyStatus").attr("style", "position: fixed; top: 0; width: 620px;")
		$("#belowStatus").attr("style", "position: relative; top: 135px;")
		$("#whitebox").attr("style", "position: absolute; z-index: 10; background-color: white; height: 115px; width: 620px; border-bottom: 2px solid #A4A4A4;")
		}
	else {
		$("#stickyactivity").attr("style", "")
		$("#stickyStatus").attr("style", "position: relative; width: 620px;") 
		$("#belowStatus").attr("style", "position: relative; top: 135px;")
		$("#whitebox").attr("style", "position: absolute; z-index: 10; background-color: white; height: 115px; width: 620px;")
		}
		
	})});