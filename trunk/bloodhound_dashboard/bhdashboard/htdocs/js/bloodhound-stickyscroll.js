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
  function stickyLogic() {
    var windowHeight = $(window).height();
    var headerHeight = $("header").height();
    var docViewTop = $(window).scrollTop();

    var headerStickyHeight = $("header #stickyStatus").height();
    var headerTop = $("header").offset().top;
    var headerBottom = headerTop + headerHeight - headerStickyHeight;

    if(windowHeight >= 768) {
      headerBottom = headerTop + $("header .nonsticky-header").height();
      $("div#breadcrumb-row > div").attr('id','oldstickyStatus');
      $("div#breadcrumb-row > div").removeClass("sticky");
      $('header .sticky-header').attr('id','stickyStatus');
    }
    else {
      $('header .sticky-header').attr('id','oldstickyStatus');
      $("header .sticky-header").removeClass("sticky");
      $("div#breadcrumb-row > div").attr('id','stickyStatus');
    }
    var stickyHeight = $("#stickyStatus").outerHeight();
    if (docViewTop > headerBottom) {
      $("#stickyStatus").addClass("sticky");
      $(".stickyOffset").css("height", stickyHeight + "px");
    }
    else {
      $("#stickyStatus").removeClass("sticky");
      $(".stickyOffset").css("height", "0px");
    }
    $("#oldstickyStatus").removeClass("sticky");
  };
  $(window).scroll(stickyLogic);
  $(window).resize(stickyLogic);
});
