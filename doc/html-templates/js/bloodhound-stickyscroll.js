$(document).ready(function stickyStatus() {
	$(window).scroll(function onScroll() {
	
	    var docViewTop = $(window).scrollTop();
	    var docViewBottom = docViewTop + $(window).height();

	    var elemTop = $("header").offset().top;
	    var elemBottom = elemTop + $("header").height();
    
		if (docViewTop > elemBottom) {
//			$("#stickyActivity").css({'position': 'fixed', 'top': '0'});
			$("#stickyStatus").css({'position': 'fixed'});
			$("#whitebox").css({'border-bottom': '2px solid #A4A4A4'});
		}
		else {
//			$("#stickyActivity").css({'position': '', 'top': ''});
			$("#stickyStatus").css({'position': ''}); 
			$("#whitebox").css({'border-bottom': ''});
			}
	});
});