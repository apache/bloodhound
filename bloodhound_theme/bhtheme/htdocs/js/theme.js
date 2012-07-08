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

$( function () {
    var qct_result = {};
    var qct_timeout = null;

    // Do not close dropdown menu if user interacts with form controls
    $('.dropdown-menu input, .dropdown-menu label, .dropdown-menu select')
        .click(function (e) { e.stopPropagation(); });

    // Install popover for create ticket shortcut
    // Important: Further options specified in markup
    $('#qct-newticket').popover({
        title : function () {
            ticket = qct_info.ticket;
            if (ticket)
              title = 'Ticket #' + qct_info.ticket;
            else
              title = 'Error creating ticket';
            return title + ' <a class="close" id="qct-alert-close" ' +
                'data-dismiss="alert" href="#">&times;</a>'
          },
        content : function () { return qct_info.msg; }
      });
    $('body').on('click.close', '#qct-alert-close', 
        function (e) { qct_alert_close() });

    // Display & hide message triggered by quick create box
    function qct_alert(msg) {
      qct_info = msg;
      jQuery('#qct-newticket').popover('show');
      if (qct_timeout)
        clearTimeout(qct_timeout);
      qct_timeout = setTimeout(qct_alert_close, 4000);
    }

    function qct_alert_close() {
      jQuery('#qct-newticket').popover('hide');
    }

    // Clear input controls inside quick create box
    function qct_clearui() {
      $('#qct-fieldset input, #qct-fieldset select').val('');
    }

    // We want to submit via #qct-create
    $('#qct-form').submit(function(e) {
      $('#qct-create').click();
      e.preventDefault();
    });

    // Install quick create box click handlers
    $('#qct-cancel').click(
        function () {
          qct_clearui();
        }
      );
    $('#qct-create').click(
        function() {
          var base_url = $('#qct-create').attr('data-target');
          $.post(base_url + '/qct', $('#qct-form').serialize(), 
              function(ticket_id) {
                qct_alert({
                    ticket: ticket_id,
                    msg: '<span class="alert alert-success" ' +
                          ' style="padding:3px"> Has been created</span>' +
                        '</span> <a href="' + base_url + '/ticket/' +
                        ticket_id + '" class="pull-right">View / Edit</a>'
                  });
              })
              .error(function(jqXHR, textStatus, errorMsg) {
                  var msg = 'Error:' + errorMsg;
                  if (textStatus === 'timeout')
                    msg = 'Request timed out';
                  else if (textStatus === 'error')
                    msg = 'Could not create ticket . Error : ' + errorMsg;
                  else if (textStatus === 'abort')
                    msg = 'Aborted request'
                  qct_alert({ 
                      ticket : null, 
                      msg : '<span class="alert alert-error"' +
                          ' style="display:block">' + msg + '</span>'
                    });
                });
          qct_clearui();
        }
      )

  })

// Event handlers for sticky panels , if any
function stickyScroll(selector) {
  
  var docViewTop = $(window).scrollTop();
  var docViewBottom = docViewTop + $(window).height();

  var elemTop = $("header").offset().top;
  var elemBottom = elemTop + $("header").height();

  var sticky_panel = $(selector);
  if (docViewTop > elemBottom) {
    var dimensions = { 
        'height' : sticky_panel.attr('data-height'), 
        'width' : sticky_panel.attr('data-width')
      }
    sticky_panel.parent().css(dimensions);
    sticky_panel.css({
        'height' : dimensions.height,
        'position': 'fixed', 
        'width' : dimensions.width
      });
    sticky_panel.find(".whitebox").css({
        'border-bottom': '2px solid #A4A4A4',
        'height' : dimensions.height,
        'width' : dimensions.width
      });
  }
  else {
    sticky_panel.parent().css({ 'height' : '' , 'width' : ''});
    sticky_panel.css({'height' : '', 'position' : '', 'width' : ''}); 
    sticky_panel.find(".whitebox").css({'border-bottom': ''});
    sticky_panel.attr({
        'data-height' : '' + sticky_panel.height() + 'px',
        'data-width' : '' + sticky_panel.width() + 'px',
      });
  }
}

function setup_sticky_panel(selector) {
  $(window).scroll(function () { stickyScroll(selector) });
  var sticky_panel = $(selector);
  $(selector + ' .whitebox').css({
      'height' : '' + sticky_panel.height() + 'px',
      'width' : '' + sticky_panel.width() + 'px'
    });
}

