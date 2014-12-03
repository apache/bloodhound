/*
	Licensed to the Apache Software Foundation (ASF) under one
	or more contributor license agreements.  See the NOTICE file
	distributed with this work for additional information
	regarding copyright ownership.  The ASF licenses this file
	to you under the Apache License, Version 2.0 (the
	"License"); you may not use this file except in compliance
	with the License.  You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

	Unless required by applicable law or agreed to in writing,
	software distributed under the License is distributed on an
	"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
	KIND, either express or implied.  See the License for the
	specific language governing permissions and limitations
	under the License.
*/

$(document).ready(function stickyStatus() {


	$(window).scroll(function onScroll() {
	
		var windowWidth = $(window).width();

		var docViewTop = $(window).scrollTop();
		var docViewBottom = docViewTop + $(window).height();

		var headerTop = $("header").offset().top;
		var headerBottom = headerTop + $("header").height();

		var statusTop = $("#stickyStatus").offset().top;
		var statusBottom = statusTop + $("#stickyStatus").height();

		var desktopStickyHeight = $("#stickyStatus").outerHeight();

		var mobileStickyHeight = $("#mobileStickyStatus").outerHeight();
	
		if(windowWidth >= 768) {
			if (docViewTop > headerBottom) {
				$("#stickyStatus").addClass("sticky");
				$(".stickyOffset").css("height", desktopStickyHeight + "px");
				console.log("I'm sticky");
			}
			else {
				$("#stickyStatus").removeClass("sticky"); 
				$(".stickyOffset").css("height", "0px");
				}
			}
		else {
			if (docViewTop > statusBottom) {
				$("#mobileStickyStatus").addClass("sticky");
				$(".stickyOffset").css("height", mobileStickyHeight + "px");
				
				console.log("Mobile sticky");
			}

			else {
				$("#mobileStickyStatus").removeClass("sticky"); 
				$(".stickyOffset").css("height", "0px");
				console.log("Mobile unsticky");
			};
			
		};
	});
});
