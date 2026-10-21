import urllib.parse
from datetime import datetime

def format_phone_number(phone):
    """Clean and format Indian mobile number with 91 country code."""
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, str(phone)))
    if len(digits) == 10:
        return "91" + digits
    elif len(digits) == 12 and digits.startswith("91"):
        return digits
    elif len(digits) > 10 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits

def generate_issue_whatsapp_message(recipient_name, recipient_id, component_name, quantity, unit, purpose, recipient_type="STUDENT", dept=""):
    """Create a formatted WhatsApp receipt message for a single issued item."""
    return generate_batch_issue_whatsapp_message(
        recipient_name=recipient_name,
        recipient_id=recipient_id,
        items_list=[{'name': component_name, 'quantity': quantity, 'unit': unit}],
        purpose=purpose,
        recipient_type=recipient_type,
        dept=dept
    )

def generate_batch_issue_whatsapp_message(recipient_name, recipient_id, items_list, purpose, recipient_type="STUDENT", dept="", lab_name="Embedded Systems Laboratory"):
    """Create a formatted WhatsApp receipt message for one or multiple issued items."""
    now_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    dept_header = lab_name.upper() if lab_name else "EMBEDDED SYSTEMS LAB"
    
    if recipient_type == "STAFF":
        title = f"SVPCET NAGPUR (IIoT) - {dept_header} FACULTY ISSUE"
        greeting = f"Respected *{recipient_name}* ({dept or 'Faculty / Staff'}),"
        salutation = f"The following equipment has been issued from the {lab_name} for your academic / lab use:"
    elif recipient_type == "OTHER_LAB":
        title = f"SVPCET NAGPUR (IIoT) - INTER-LAB HARDWARE TRANSFER"
        greeting = f"Attention: *{recipient_name}* ({dept or 'Department'}),"
        salutation = f"The following equipment has been borrowed from the {lab_name}:"
    else:
        title = f"SVPCET NAGPUR (IIoT) - {dept_header} ISSUE RECEIPT"
        greeting = f"Hello *{recipient_name}* (UID: *{recipient_id}*),"
        salutation = "You have been issued the following laboratory items:"

    if len(items_list) == 1:
        it = items_list[0]
        items_block = f"📦 *Item:* {it['name']}\n🔢 *Quantity:* {it['quantity']} {it['unit']}"
    else:
        items_block = f"📦 *Issued Items ({len(items_list)} Items):*\n"
        for idx, it in enumerate(items_list, 1):
            items_block += f"  {idx}. *{it['name']}* — {it['quantity']} {it['unit']}\n"
        items_block = items_block.rstrip()

    msg = (
        f"🏛 *{title}*\n\n"
        f"{greeting}\n\n"
        f"{salutation}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{items_block}\n"
        f"📅 *Date & Time:* {now_str}\n"
        f"🎯 *Purpose:* {purpose or 'Embedded Systems / IoT Practical'}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ *Note:* Please handle components carefully and return after practical session.\n\n"
        f"— *{lab_name}, Dept. of Industrial IoT*\n"
        f"*St. Vincent Pallotti College of Engg. & Tech., Nagpur*"
    )
    return msg

def generate_return_whatsapp_message(recipient_name, recipient_id, component_name, total_qty, unit, good_qty, damaged_qty, missing_qty, remarks, recipient_type="STUDENT", dept=""):
    """Create a formatted WhatsApp receipt message for returned items."""
    now_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    breakdown = f"  • Working/Good: {good_qty} {unit}\n"
    if damaged_qty > 0:
        breakdown += f"  • ⚠️ Damaged: {damaged_qty} {unit}\n"
    if missing_qty > 0:
        breakdown += f"  • ❌ Missing/Lost: {missing_qty} {unit}\n"

    status_str = "Returned in Full Good Condition" if (damaged_qty == 0 and missing_qty == 0) else "Returned with Issues / Defect Recorded"

    if recipient_type == "STAFF":
        title = "SVPCET NAGPUR (IIoT) - EMBEDDED SYSTEMS LAB RETURN RECEIPT"
        greeting = f"Respected *{recipient_name}*,"
    elif recipient_type == "OTHER_LAB":
        title = "SVPCET NAGPUR (IIoT) - INTER-LAB RETURN RECEIPT"
        greeting = f"Attention: *{recipient_name}*,"
    else:
        title = "SVPCET NAGPUR (IIoT) - EMBEDDED SYSTEMS LAB RETURN RECEIPT"
        greeting = f"Hello *{recipient_name}* (UID: *{recipient_id}*),"

    msg = (
        f"🏛 *{title}*\n\n"
        f"{greeting}\n\n"
        f"Your equipment return has been successfully acknowledged:\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Item:* {component_name}\n"
        f"🔢 *Total Accounted:* {total_qty} {unit}\n"
        f"📊 *Breakdown:*\n{breakdown}"
        f"📅 *Return Date:* {now_str}\n"
        f"📌 *Status:* {status_str}\n"
    )
    if remarks:
        msg += f"📝 *Remarks:* {remarks}\n"
        
    msg += (
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Thank you for using the Embedded Systems Lab facilities.\n\n"
        f"— *Embedded Systems Lab, Dept. of Industrial IoT*\n"
        f"*St. Vincent Pallotti College of Engg. & Tech., Nagpur*"
    )
    return msg

def get_whatsapp_url(phone, message_text):
    """Generate direct WhatsApp Web/App click-to-chat URL."""
    clean_phone = format_phone_number(phone)
    if not clean_phone:
        return ""
    encoded_text = urllib.parse.quote(message_text)
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"
