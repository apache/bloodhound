function emptyTable(numOfRows,product,milestones,components,href,token) {
    /*
    This function will be invoked from the BatchCreateTickets wiki macro.
    The wiki macro will send the relevant details to create the empty ticket table within the wiki.
    Then this function will generate the empty ticket table containing appropriate number of rows to enter ticket data.
     */
	created_rows=numOfRows;
	form_token = token.split(";")[0].split("=")[1];
	if(numOfRows == ""){
		alert("Enter the ticket batch size.")
	}
	else if(numOfRows != "" && document.getElementById("empty-table") == null){
	var contentDiv = document.getElementById("div-empty-table");
    var headers = {"ticket":"","summary":"Summary","description":"Description","product":"Product","priority":"Priority","milestone":"Milestone","component":"Component"}
	priorities = ["blocker", "critical", "major", "minor", "trivial"];
	types = ["defect", "enhancement", "task"];
	
	var div = document.createElement("div");
	div.setAttribute("class","span12");
	div.setAttribute("id","empty-table");
	var h5 = document.createElement("h5");
	h5.appendChild(document.createTextNode("Batch Create Tickets"));
	div.appendChild(h5);
	
	var form = document.createElement("form");
	form.setAttribute("id","bct-form");
	form.setAttribute("name","bct");
	form.setAttribute("method","post");
	
	var div_token = document.createElement("div");
	var form_token_val = document.createElement("input");
	form_token_val.setAttribute("type","hidden");
	form_token_val.setAttribute("name","__FORM_TOKEN");
	form_token_val.setAttribute("value",form_token);
	div_token.appendChild(form_token_val);
	form.appendChild(div_token);
	
	var table = document.createElement("table");
	table.setAttribute("class","listing tickets table table-bordered table-condensed query");
	table.setAttribute("style","border-radius: 0px 0px 4px 4px");
	
	var tr = document.createElement("tr");
	tr.setAttribute("class","trac-columns");
	for (header in headers){
		font = document.createElement("font");
		font.setAttribute("color","#1975D1");
		font.appendChild(document.createTextNode(headers[header]))
		th = document.createElement("th");
		th.appendChild(font);
		tr.appendChild(th);
	}
	table.appendChild(tr);
	
	tbody = document.createElement("tbody");
	for (i=0;i<numOfRows;i++){
		tr_rows = document.createElement("tr");
		for (header in headers){
			if(header == "ticket"){
				td_row = document.createElement("td");
				input_ticket = document.createElement("input");
				input_ticket.setAttribute("type","checkbox");
				input_ticket.setAttribute("id","field-ticket"+i);
				input_ticket.setAttribute("class","input-block-level");
				input_ticket.setAttribute("name","field_ticket"+i);
				td_row.appendChild(input_ticket);
				tr_rows.appendChild(td_row);
			}
			else if (header == "summary"){
				td_row = document.createElement("td");
				input_summary = document.createElement("input");
				input_summary.setAttribute("type","text");
				input_summary.setAttribute("id","field-summary"+i);
				input_summary.setAttribute("class","input-block-level");
				input_summary.setAttribute("name","field_summary"+i);
				td_row.appendChild(input_summary);
				tr_rows.appendChild(td_row);
			}
			else if (header == "description") {
				td_row = document.createElement("td");
				input_description = document.createElement("textarea");
				input_description.setAttribute("id","field-description"+i);
				input_description.setAttribute("class","input-block-level");
				input_description.setAttribute("name","field_description"+i);
				input_description.setAttribute("rows","2");
				input_description.setAttribute("cols","28");
				td_row.appendChild(input_description);
				tr_rows.appendChild(td_row);
			}
			else if (header == "priority") {
				td_row = document.createElement("td");
				input_priority = document.createElement("select");
				input_priority.setAttribute("id","field-priority"+i);
				input_priority.setAttribute("class","input-block-level");
				input_priority.setAttribute("name","field_priority"+i);
				for (priority in priorities){
					option = document.createElement("option");
					option.setAttribute("value",priorities[priority]);
					option.appendChild(document.createTextNode(priorities[priority]));
					input_priority.appendChild(option);
				}
				td_row.appendChild(input_priority);
				tr_rows.appendChild(td_row);
			}
			else if (header == "product") {
				td_row = document.createElement("td");
				field_product = document.createElement("select");
				field_product.setAttribute("id","field-product"+i);
				field_product.setAttribute("class","input-block-level");
				field_product.setAttribute("name","field_product"+i);
				for (p in product){
					option = document.createElement("option");
					option.setAttribute("value",(product[p])[0]);
					option.appendChild(document.createTextNode((product[p])[1]));
					field_product.appendChild(option);
				}
				td_row.appendChild(field_product);
				tr_rows.appendChild(td_row);
			}
			else if (header == "milestone"){
				td_row = document.createElement("td");
				field_milestone = document.createElement("select");
				field_milestone.setAttribute("id","field-milestone"+i);
				field_milestone.setAttribute("class","input-block-level");
				field_milestone.setAttribute("name","field_milestone"+i);
				for (milestone in milestones){
					option = document.createElement("option");
					option.setAttribute("value",(milestones[milestone])[0]);
					option.appendChild(document.createTextNode((milestones[milestone])[0]));
					field_milestone.appendChild(option);
				}
				td_row.appendChild(field_milestone);
				tr_rows.appendChild(td_row);
			}
			else if (header == "component"){
				td_row = document.createElement("td");
				field_component = document.createElement("select");
				field_component.setAttribute("id","field-component"+i);
				field_component.setAttribute("class","input-block-level");
				field_component.setAttribute("name","field_component"+i);
				for (component in components){
					option = document.createElement("option");
					option.setAttribute("value",(components[component])[0]);
					option.appendChild(document.createTextNode((components[component])[0]));
					field_component.appendChild(option);
				}
				td_row.appendChild(field_component);
				tr_rows.appendChild(td_row);
			}
		}
		tbody.appendChild(tr_rows);
	}
	table.appendChild(tbody);
	form.appendChild(table);

	remove_row_button = document.createElement("button");
	remove_row_button.setAttribute("class","btn pull-right");
	remove_row_button.setAttribute("type","button");
	remove_row_button.addEventListener("click", function(event) {
  		numOfRows=parseInt(numOfRows)-parseInt(remove_row_btn_action(numOfRows));
  		event.preventDefault();
	});
	remove_row_button.setAttribute("id","bct-rmv-empty-row");
	remove_row_button.appendChild(document.createTextNode("-"));
	form.appendChild(remove_row_button);
	
	add_row_button = document.createElement("button");
	add_row_button.setAttribute("class","btn pull-right");
	add_row_button.setAttribute("type","button");
	add_row_button.addEventListener("click", function(event) {
  		add_row_btn_action(product,milestones,components,created_rows);
  		numOfRows=parseInt(numOfRows)+1;
  		created_rows=parseInt(created_rows)+1;
  		event.preventDefault();
	});
	add_row_button.setAttribute("id","bct-add-empty-row");
	add_row_button.appendChild(document.createTextNode("+"));
	form.appendChild(add_row_button);	

    submit_button = document.createElement("button");
	submit_button.setAttribute("class","btn pull-right");
	submit_button.setAttribute("type","button");
	submit_button.addEventListener("click", function(event) {
		var empty_row=false;
		var cnt=0;
		for (var k = 0; k <parseInt(numOfRows)+parseInt(cnt); k++) {
			var element = document.getElementById("field-summary"+k);
			if(element==null){
				cnt=parseInt(cnt)+1;
				continue;
			}
			
			var summary_val=document.getElementById("field-summary"+k).value;
			if(summary_val==""){
				var line_number = parseInt(k)+1;
				var confirmation = confirm("Summery field of one or more tickets are empty. They will not get created!");
				empty_row=true;
				break;
			}
		};
		if(confirmation == true || !empty_row){
			submit_btn_action();
  			event.preventDefault();
		}
	});
	submit_button.setAttribute("id","bct-create");
	submit_button.setAttribute("data-target",href);
	submit_button.appendChild(document.createTextNode("save"));
	form.appendChild(submit_button);	
	
	cancle_button = document.createElement("button");
	cancle_button.setAttribute("class","btn pull-right");
	cancle_button.setAttribute("type","button");
	cancle_button.setAttribute("onclick","deleteForm()");
	cancle_button.appendChild(document.createTextNode("cancel"));
	form.appendChild(cancle_button);
	
	div.appendChild(form);
	contentDiv.appendChild(div);
	}

}

function submitForm(){
	document.getElementById("bct-form").submit();
}

function deleteForm(){
    /*
    This function will invoke when the user clicks on cancel button under the empty table.
    Then this function will remove the empty table from the wiki.
     */
	document.getElementById("empty-table").remove();
}

function submit_btn_action() {
    /*
    This function will send a HTTP POST request to the backend.
    The form containing the empty table and its data will be submitted.
    Then the empty table will be replaced with the ticket table containing details of the created tickets.
     */
    // data-target is the base url for the product in current scope
	var product_base_url = $('#bct-create').attr('data-target');
    if (product_base_url === '/')
        product_base_url = '';
        $.post(product_base_url , $('#bct-form').serialize(),
        function(ticket) {
			deleteForm();

			var headers = {"ticket":"Ticket","summary":"Summary","product":"Product","status":"Status","milestone":"Milestone","component":"Component"}
			var contentDiv = document.getElementById("div-empty-table");
			var div = document.createElement("div");
			div.setAttribute("class","span12");
			var h5 = document.createElement("h5");
			h5.appendChild(document.createTextNode("Created Tickets"));
			div.appendChild(h5);
			var table = document.createElement("table");
			table.setAttribute("class","listing tickets table table-bordered table-condensed query");
			table.setAttribute("style","border-radius: 0px 0px 4px 4px");
			tr = document.createElement("tr");
			tr.setAttribute("class","trac-columns");
			
			for (header in headers){
				th = document.createElement("th");
				font = document.createElement("font");
				font.setAttribute("color","#1975D1");
				font.appendChild(document.createTextNode(headers[header]))
				th = document.createElement("th");
				th.appendChild(font);
				tr.appendChild(th);
			}
			table.appendChild(tr);
			
			for ( i=0 ; i<Object.keys(ticket.tickets).length ; i++ ){
				tr = document.createElement("tr");
				for (j=0;j<6;j++){
					if(j==0){
						td = document.createElement("td");
						a = document.createElement("a");
						tkt = JSON.parse(ticket.tickets[i]);
						a.setAttribute("href",tkt.url);
						a.appendChild(document.createTextNode("#"+tkt.id));
						td.appendChild(a);
					}
					else if(j==1){
						td = document.createElement("td");
						a = document.createElement("a");
						tkt = JSON.parse(ticket.tickets[i]);
						a.setAttribute("href",tkt.url);
						a.appendChild(document.createTextNode(tkt.summary));
						td.appendChild(a);
					}
					else if(j==2){
						td = document.createElement("td");
						tkt = JSON.parse(ticket.tickets[i]);
						td.appendChild(document.createTextNode(tkt.product));
					}
					else if(j==3){
						td = document.createElement("td");
						tkt = JSON.parse(ticket.tickets[i]);
						td.appendChild(document.createTextNode(tkt.status));
					}
					else if(j==4){
						td = document.createElement("td");
						tkt = JSON.parse(ticket.tickets[i]);
						td.appendChild(document.createTextNode(tkt.milestone));
					}
					else if(j==5){
						td = document.createElement("td");
						tkt = JSON.parse(ticket.tickets[i]);
						td.appendChild(document.createTextNode(tkt.component));
					}
					tr.appendChild(td);
				}
				table.appendChild(tr);
			}
			div.appendChild(table);
			contentDiv.appendChild(div);     
        });
}

function add_row_btn_action(product,milestones,components,i){
    /*
    This function will be called when the users add a new row to the empty table.
    The new empty row will be always appended to the end row of the empty table.
     */
	var headers = {"ticket":"","summary":"Summary","description":"Description","product":"Product","priority":"Priority","milestone":"Milestone","component":"Component"}
	//var statuses = ["new", "accepted", "assigned", "closed", "reopened"];
	var priorities = ["blocker", "critical", "major", "minor", "trivial"];
	var types = ["defect", "enhancement", "task"];

    tr_rows = document.createElement("tr");

    for (header in headers){
    	if(header == "ticket"){
			td_row = document.createElement("td");
			input_ticket = document.createElement("input");
			input_ticket.setAttribute("type","checkbox");
			input_ticket.setAttribute("id","field-ticket"+i);
			input_ticket.setAttribute("class","input-block-level");
			input_ticket.setAttribute("name","field_ticket"+i);
			td_row.appendChild(input_ticket);
			tr_rows.appendChild(td_row);
		}
		else if (header == "summary"){
				td_row = document.createElement("td");
				input_summary = document.createElement("input");
				input_summary.setAttribute("type","text");
				input_summary.setAttribute("id","field-summary"+i);
				input_summary.setAttribute("class","input-block-level");
				input_summary.setAttribute("name","field_summary"+i);
				td_row.appendChild(input_summary);
				tr_rows.appendChild(td_row);
		}
		else if (header == "description") {
			td_row = document.createElement("td");
			input_description = document.createElement("textarea");
			input_description.setAttribute("id","field-description"+i);
			input_description.setAttribute("class","input-block-level");
			input_description.setAttribute("name","field_description"+i);
			input_description.setAttribute("rows","2");
			input_description.setAttribute("cols","28");
			td_row.appendChild(input_description);
			tr_rows.appendChild(td_row);
		}
		else if (header == "priority") {
			td_row = document.createElement("td");
			input_priority = document.createElement("select");
			input_priority.setAttribute("id","field-priority"+i);
			input_priority.setAttribute("class","input-block-level");
			input_priority.setAttribute("name","field_priority"+i);
			for (priority in priorities){
				option = document.createElement("option");
				option.setAttribute("value",priorities[priority]);
				option.appendChild(document.createTextNode(priorities[priority]));
				input_priority.appendChild(option);
			}
			td_row.appendChild(input_priority);
			tr_rows.appendChild(td_row);
		}
		else if (header == "product") {
			td_row = document.createElement("td");
			field_product = document.createElement("select");
			field_product.setAttribute("id","field-product"+i);
			field_product.setAttribute("class","input-block-level");
			field_product.setAttribute("name","field_product"+i);
			for (p in product){
				option = document.createElement("option");
				option.setAttribute("value",(product[p])[0]);
				option.appendChild(document.createTextNode((product[p])[1]));
				field_product.appendChild(option);
			}
			td_row.appendChild(field_product);
			tr_rows.appendChild(td_row);
		}
		else if (header == "milestone"){
			td_row = document.createElement("td");
			field_milestone = document.createElement("select");
			field_milestone.setAttribute("id","field-milestone"+i);
			field_milestone.setAttribute("class","input-block-level");
			field_milestone.setAttribute("name","field_milestone"+i);
			for (milestone in milestones){
				option = document.createElement("option");
				option.setAttribute("value",(milestones[milestone])[0]);
				option.appendChild(document.createTextNode((milestones[milestone])[0]));
				field_milestone.appendChild(option);
			}
			td_row.appendChild(field_milestone);
			tr_rows.appendChild(td_row);
		}
		else if (header == "component"){
			td_row = document.createElement("td");
			field_component = document.createElement("select");
			field_component.setAttribute("id","field-component"+i);
			field_component.setAttribute("class","input-block-level");
			field_component.setAttribute("name","field_component"+i);
			for (component in components){
				option = document.createElement("option");
				option.setAttribute("value",(components[component])[0]);
				option.appendChild(document.createTextNode((components[component])[0]));
				field_component.appendChild(option);
			}
			td_row.appendChild(field_component);
			tr_rows.appendChild(td_row);
		}
	}
	document.getElementById("empty-table").childNodes[1].childNodes[1].childNodes[1].appendChild(tr_rows);
}

function remove_row_btn_action(numOfRows){
    /*
    This function will be called when the user removes a table row of the empty table.
     */
	var cnt=0;
	for(var i=0;i<parseInt(numOfRows)-parseInt(cnt);i++){
		if(document.getElementById("empty-table").childNodes[1].childNodes[1].childNodes[1].childNodes[i].childNodes[0].childNodes[0].checked){
			document.getElementById("empty-table").childNodes[1].childNodes[1].childNodes[1].childNodes[i].remove();
			cnt=cnt+1;
			i--;
		}
	}
	return cnt;
}

function display_created_tickets(ticket) {
    /*
    Take ticket data sent through the CreatedTickets wiki macro and display those data as a ticket table within the wiki.
    This function will create a div element containing the ticket table data and append that div to div with
    "div-created-ticket-table".
     */
	var headers = {"ticket":"Ticket","summary":"Summary","product":"Product","status":"Status","milestone":"Milestone","component":"Component"}
	var contentDiv = document.getElementById("div-created-ticket-table");
	var div = document.createElement("div");
	div.setAttribute("class","span12");
	var h5 = document.createElement("h5");
	h5.appendChild(document.createTextNode("Created Tickets"));
	div.appendChild(h5);
	var table = document.createElement("table");
	table.setAttribute("class","listing tickets table table-bordered table-condensed query");
	table.setAttribute("style","border-radius: 0px 0px 4px 4px");
	tr = document.createElement("tr");
	tr.setAttribute("class","trac-columns");
			
	for (header in headers){
		th = document.createElement("th");
		font = document.createElement("font");
		font.setAttribute("color","#1975D1");
		font.appendChild(document.createTextNode(headers[header]))
		th = document.createElement("th");
		th.appendChild(font);
		tr.appendChild(th);
	}
	table.appendChild(tr);
	for ( i=0 ; i<Object.keys(ticket.tickets).length ; i++ ){
		tr = document.createElement("tr");
		for (j=0;j<6;j++){
			if(j==0){
				td = document.createElement("td");
				a = document.createElement("a");
				tkt = JSON.parse(ticket.tickets[i]);
				a.setAttribute("href",tkt.url);
				a.appendChild(document.createTextNode("#"+tkt.id));
				td.appendChild(a);
			}
			else if(j==1){
				td = document.createElement("td");
				a = document.createElement("a");
				tkt = JSON.parse(ticket.tickets[i]);
				a.setAttribute("href",tkt.url);
				a.appendChild(document.createTextNode(tkt.summary));
				td.appendChild(a);
			}
			else if(j==2){
				td = document.createElement("td");
				tkt = JSON.parse(ticket.tickets[i]);
				td.appendChild(document.createTextNode(tkt.product));
			}
			else if(j==3){
				td = document.createElement("td");
				tkt = JSON.parse(ticket.tickets[i]);
				td.appendChild(document.createTextNode(tkt.status));
			}
			else if(j==4){
				td = document.createElement("td");
				tkt = JSON.parse(ticket.tickets[i]);
				td.appendChild(document.createTextNode(tkt.milestone));
			}
			else if(j==5){
				td = document.createElement("td");
				tkt = JSON.parse(ticket.tickets[i]);
				td.appendChild(document.createTextNode(tkt.component));
			}
			tr.appendChild(td);
		}
		table.appendChild(tr);
	}
	div.appendChild(table);
	contentDiv.appendChild(div);     
 }