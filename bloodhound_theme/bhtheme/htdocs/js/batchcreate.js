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

/*
 This function will be invoked from the BatchCreateTickets wiki macro.
 The wiki macro will send the relevant details to create the empty ticket table within the wiki.
 Then this function will generate the empty ticket table containing appropriate number of rows to enter ticket data.
 */
function emptyTable(numOfRows, product, milestones, components, href, token, unique_key) {

  var created_rows = numOfRows;
  var form_token = token.split(";")[0].split("=")[1];

  var headers = {
    "ticket": "", "summary": "Summary", "description": "Description",
    "priority": "Priority", "milestone": "Milestone", "component": "Component"
  };
  var priorities = ["blocker", "critical", "major", "minor", "trivial"];
  var types = ["defect", "enhancement", "task"];

  var contentDiv = $('#div-empty-table' + unique_key);

  var div = $('<div/>', {
    'id': 'empty-table' + unique_key
  }).appendTo(contentDiv);

  $('<div/>', {
    'id': 'numrows' + unique_key,
    'class': 'numrows'
  }).html('(' + numOfRows + ' total rows.)').appendTo(div);

  var form = $('<form/>', {
    'id': 'bct-form' + unique_key,
    'name': 'bct',
    'method': 'post',
    'style': 'margin-bottom:60px'
  }).appendTo(div);

  $('<input/>', {
    'type': 'hidden',
    'name': '__FORM_TOKEN',
    'value': form_token
  }).appendTo($('<div>').appendTo(form));

  var table = $('<table/>', {
    'id': 'table' + unique_key,
    'class': 'table table-condensed tickets'
  }).appendTo(form);

  var thead = $('<thead/>').appendTo(table);
  var header_tr = $('<tr/>', {
    'class': 'row'
  }).appendTo(thead);

  for (header in headers) {
    var th = $('<th/>').html(headers[header]).appendTo(header_tr);
  }

  var tbody = $('<tbody>', {
    'id': 'tbody' + unique_key
  }).appendTo(table);

  for (var i = 0; i < numOfRows; i++) {

    var tr_rows = $('<tr>', {
      'class': 'row'
    }).appendTo(tbody);

    for (var header in headers) {
      var td;
      if (header == "ticket") {

        td = $('<td>').appendTo(tr_rows);

        var button = $('<button/>', {
          'id': 'bct-rmv-empty-row' + i + '' + unique_key,
          'type': 'button',
          'class': 'btn pull-right',
          'click': function () {
            numOfRows = $("#tbody" + unique_key).children().length - 1;
            $('#numrows' + unique_key).empty();
            $('#numrows' + unique_key).html('(' + numOfRows + ' total rows.)');
            $(this).parent().parent().remove();
          }
        }).appendTo(td);

        $('<i/>', {
          'class': 'icon-trash'
        }).appendTo(button);

      } else if (header == "summary") {

        td = $('<td>').appendTo(tr_rows);
        $('<input/>', {
          'id': 'field-summary' + unique_key + '-' + i,
          'type': 'text',
          'name': 'field_summary' + i,
          'class': 'summary'
        }).appendTo(td);

      } else if (header == "description") {

        td = $('<td>').appendTo(tr_rows);
        $('<textarea/>', {
          'id': 'field-description' + unique_key + '-' + i,
          'name': 'field_description' + i,
          'class': 'description'
        }).appendTo(td);

      } else if (header == "priority") {

        td = $('<td>').appendTo(tr_rows);
        var input_priority = $('<select/>', {
          'id': 'field-priority' + unique_key + '-' + i,
          'name': 'field_priority' + i,
          'class': 'priority'
        }).appendTo(td);

        for (var priority in priorities) {
          $('<option/>', {
            'value': priorities[priority]
          }).html(priorities[priority]).appendTo(input_priority);
        }

      } else if (header == "milestone") {

        td = $('<td>').appendTo(tr_rows);
        var field_milestone = $('<select/>', {
          'id': 'field-milestone' + unique_key + '-' + i,
          'name': 'field_milestone' + i,
          'class': 'milestone'
        }).appendTo(td);

        for (var milestone in milestones) {
          $('<option/>', {
            'value': (milestones[milestone])[0]
          }).html((milestones[milestone])[0]).appendTo(field_milestone);
        }

      } else if (header == "component") {

        td = $('<td>').appendTo(tr_rows);
        var field_component = $('<select/>', {
          'id': 'field-component' + unique_key + '-' + i,
          'name': 'field_component' + i,
          'class': 'component'
        }).appendTo(td);

        for (var component in components) {
          $('<option/>', {
            'value': (components[component])[0]
          }).html((components[component])[0]).appendTo(field_component);
        }
      }
    }
  }

  $('<button/>', {
    'id': 'bct-add-empty-row' + unique_key,
    'type': 'button',
    'class': 'btn pull-right',
    'click': function () {
      add_row_btn_action(products, milestones, components, created_rows, unique_key, headers, tbody);
      numOfRows = parseInt(numOfRows) + 1;
      created_rows = parseInt(created_rows) + 1;
    }
  }).html('+').appendTo(form);

  $('<button/>', {
    'id': 'bct-create' + unique_key,
    'type': 'button',
    'class': 'btn pull-right',
    'data-target': href,
    'click': function () {
      var empty_row = false;
      var cnt = 0;
      for (var k = 0; k < parseInt(numOfRows) + parseInt(cnt); k++) {

        var element = $("#field-summary" + k);
        if (element == null) {
          cnt = parseInt(cnt) + 1;
          continue;
        }

        var summary_val = element.val();
        if (summary_val == "") {
          var line_number = parseInt(k) + 1;
          var confirmation = confirm("Summery field of one or more tickets are empty. " +
            "They will not get created!");
          empty_row = true;
          break;
        }
      }
      if (confirmation == true || !empty_row) {
        submit_btn_action(unique_key);
      }
    }
  }).html('Create tickets').appendTo(form);

  $('<button/>', {
    'type': 'hidden',
    'class': 'btn pull-right',
    'click': function () {
      deleteForm(unique_key);
    }
  }).html('cancel').appendTo(form);
  //todo remove wiki macro from wiki content

}

function submitForm() {
  document.getElementById("bct-form").submit();
}

/*
 Then this function will remove the empty table from the wiki.
 */
function deleteForm(unique_key) {
  $("#empty-table" + unique_key).remove();
}

/*
 This function will send a HTTP POST request to the backend.
 The form containing the empty table and its data will be submitted.
 Then the empty table will be replaced with the ticket table containing details of the created tickets.
 */
function submit_btn_action(unique_key) {

  // data-target is the base url for the product in current scope
  var product_base_url = $('#bct-create' + unique_key).attr('data-target');

  $.post(product_base_url, $('#bct-form' + unique_key).serialize(),
    function (ticket) {
      deleteForm(unique_key);

      var headers = {
        "ticket": "Ticket", "summary": "Summary", "product": "Product", "status": "Status",
        "milestone": "Milestone", "component": "Component"
      };

      var contentDiv = $("#div-empty-table" + unique_key);

      var div = $('<div/>').appendTo(contentDiv);

      $('<div/>', {
        'class': 'numrows'
      }).html('(' + ticket.tickets.length + ' total rows.)').appendTo(div);

      var table = $('<table/>', {
        'class': 'table table-condensed tickets'
      }).appendTo(div);

      var thead = $('<thead/>').appendTo(table);
      var header_tr = $('<tr/>').appendTo(thead);

      for (var header in headers) {
        var th = $('<th/>').html(headers[header]).appendTo(header_tr);
      }

      for (var json_ticket in ticket.tickets) {
        var tr = $('<tr/>').appendTo(table);
        var tkt = JSON.parse(ticket.tickets[json_ticket]);
        for (var j = 0; j < 6; j++) {
          var td = $('<td/>').appendTo(tr);
          if (j == 0) {
            if (json_ticket == 0) {
             td.html(tkt.product)
            }
          } else if (j < 3) {
            $('<a/>', {
              'href': tkt.url
            }).html(j == 1 ? "#" + tkt.id : tkt.summary).appendTo(td);
          } else {
            td.html(j == 3 ? tkt.status : (j == 4 ? tkt.milestone : tkt.component))
          }
        }
      }
    });
}

/*
 This function will be called when the users add a new row to the empty table.
 The new empty row will be always appended to the end row of the empty table.
 */
function add_row_btn_action(products, milestones, components, i, random, headers, tbody) {

  var statuses = ["new", "accepted", "assigned", "closed", "reopened"];
  var priorities = ["blocker", "critical", "major", "minor", "trivial"];
  var types = ["defect", "enhancement", "task"];

  var tr = $('<tr/>').appendTo(tbody);

  for (var header in headers) {

    var td = $('<td/>').appendTo(tr);
    var unique_key = random + '-' + i;

    if (header == 'ticket') {
      $('<input/>', {
        'id': 'field-ticket' + unique_key,
        'name': 'field_ticket' + unique_key,
        'type': 'checkbox'
      }).appendTo(td);
    } else if (header == "summary") {

      $('<input/>', {
        'id': 'field-summary' + unique_key,
        'name': 'field_summary' + unique_key,
        'type': 'text'
      }).appendTo(td);
    } else if (header == "description") {

      $('<textarea/>', {
        'id': 'field-description' + unique_key,
        'name': 'field_description' + unique_key
      }).appendTo(td);
    } else if (header == "priority") {

      var input_priority = $('<select/>', {
        'id': 'field-priority' + unique_key,
        'name': 'field_priority' + unique_key
      }).appendTo(td);
      for (var priority in priorities) {
        $('<option/>', {
          'value': priorities[priority]
        }).html(priorities[priority]).appendTo(input_priority);
      }
    } else if (header == "product") {

      var field_product = $('<select/>', {
        'id': 'field-product' + unique_key,
        'name': 'field_product' + unique_key
      }).appendTo(td);
      for (var product in products) {
        $('<option/>', {
          'value': (products[product])[0]
        }).html((products[product])[1]).appendTo(field_product);
      }
    } else if (header == "milestone") {

      var field_milestone = $('<select/>', {
        'id': 'field-milestone' + unique_key,
        'name': 'field_milestone' + unique_key
      }).appendTo(td);
      for (var milestone in milestones) {
        $('<option/>', {
          'value': (milestones[milestone])[0]
        }).html((milestones[milestone])[0]).appendTo(field_milestone);
      }
    } else if (header == "component") {

      var field_component = $('<select/>', {
        'id': 'field-component' + unique_key,
        'name': 'field_component' + unique_key
      }).appendTo(td);
      for (var component in components) {
        $('<option/>', {
          'value': (components[component])[0]
        }).html((components[component])[0]).appendTo(field_component);
      }
    }
  }
}

/*
 This function will be called when the user removes a table row of the empty table.
 */
function remove_row_btn_action(numOfRows, unique_key) {
  var cnt = 0;
  for (var i = 0; i < parseInt(numOfRows) - parseInt(cnt); i++) {
    if (document.getElementById('empty-table' + unique_key).childNodes[1].childNodes[1].childNodes[1].childNodes[i].childNodes[0].childNodes[0].checked) {
      document.getElementById('empty-table' + unique_key).childNodes[1].childNodes[1].childNodes[1].childNodes[i].remove();
      cnt = cnt + 1;
      i--;
    }
  }
  return cnt;
}

/*
 Take ticket data sent through the CreatedTickets wiki macro and display those data as a ticket table within the wiki.
 This function will create a div element containing the ticket table data and append that div to div with
 "div-created-ticket-table".
 */
function display_created_tickets(tickets, unique_key) {

  var headers = {
    "product": "", "ticket": "Ticket", "summary": "Summary", "status": "Status",
    "milestone": "Milestone", "component": "Component"
  };

  var contentDiv = $('#div-created-ticket-table' + unique_key);
  var div = $('<div/>').appendTo(contentDiv);

  $('<div/>', {
    'class': 'numrows'
  }).html('(' + tickets.length + ' total rows.)').appendTo(div);

  var table = $('<table/>', {
    'class': 'table table-condensed tickets'
  }).appendTo(div);

  var thead = $('<thead/>').appendTo(table);
  var header_tr = $('<tr/>').appendTo(thead);

  for (var header in headers) {
    var th = $('<th/>').html(headers[header]).appendTo(header_tr);
  }

  for (var index in tickets) {
    var tr = $('<tr/>').appendTo(table);
    var tkt = JSON.parse(tickets[index]);

    for (var j = 0; j < 6; j++) {
      var td = $('<td/>');
      if (j == 0) {
        if (index == 0) {
          td.html(tkt.product)
        }
      } else if (j < 3) {
        $('<a/>', {
          'href': tkt.url
        }).html(j == 1 ? "#" + tkt.id : tkt.summary).appendTo(td);
      } else {
        td.html(j == 3 ? tkt.status : (j == 4 ? tkt.milestone : tkt.component))
      }
      td.appendTo(tr)
    }
  }
}