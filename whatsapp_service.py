import urllib.parse
from datetime import datetime, timezone, timedelta

# Indian Standard Time (IST) = UTC + 05:30
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Return current datetime in Indian Standard Time (IST)."""
    return datetime.now(IST)

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

def generate_issue_whatsapp_message(recipient_name, recipient_id, component_name, quantity, unit, purpose, recipient_type="STUDENT", dept="", expected_return_date=None):
    """Create a formatted WhatsApp receipt message for a single issued item."""
    return generate_batch_issue_whatsapp_message(
        recipient_name=recipient_name,
        recipient_id=recipient_id,
        items_list=[{'name': component_name, 'quantity': quantity, 'unit': unit}],
        purpose=purpose,
        recipient_type=recipient_type,
        dept=dept,
        expected_return_date=expected_return_date
    )

def generate_batch_issue_whatsapp_message(recipient_name, recipient_id, items_list, purpose, recipient_type="STUDENT", dept="", lab_name="Embedded Systems Laboratory", expected_return_date=None):
    """Create a formatted WhatsApp receipt message for one or multiple issued items."""
    now_str = get_ist_now().strftime("%d-%m-%Y %I:%M %p")
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

    date_block = f"📅 *Issue Date & Time:* {now_str}\n"
    if expected_return_date:
        date_block += f"⏳ *Expected Return Date:* {expected_return_date}\n"

    msg = (
        f"🏛 *{title}*\n\n"
        f"{greeting}\n\n"
        f"{salutation}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{items_block}\n"
        f"{date_block}"
        f"🎯 *Purpose:* {purpose or 'Embedded Systems / IoT Practical'}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ *Note:* Please handle components carefully and return on or before the due date.\n\n"
        f"— *{lab_name}, Dept. of Industrial IoT*\n"
        f"*St. Vincent Pallotti College of Engg. & Tech., Nagpur*"
    )
    return msg

def generate_return_whatsapp_message(recipient_name, recipient_id, component_name, total_qty, unit, good_qty, damaged_qty, missing_qty, remarks, recipient_type="STUDENT", dept="", consumed_qty=0):
    """Create a formatted WhatsApp receipt message for returned items."""
    now_str = get_ist_now().strftime("%d-%m-%Y %I:%M %p")
    breakdown = ""
    if good_qty > 0:
        breakdown += f"  • ✅ Working / Good Condition: {good_qty} {unit}\n"
    if consumed_qty > 0:
        breakdown += f"  • 📦 Consumed / Used in Practical: {consumed_qty} {unit}\n"
    if damaged_qty > 0:
        breakdown += f"  • ⚠️ Damaged: {damaged_qty} {unit}\n"
    if missing_qty > 0:
        breakdown += f"  • ❌ Missing / Lost: {missing_qty} {unit}\n"
    if not breakdown:
        breakdown = f"  • Working / Good: {good_qty} {unit}\n"

    if damaged_qty == 0 and missing_qty == 0 and consumed_qty == 0:
        status_str = "Returned in Full Good Condition"
    elif consumed_qty == total_qty:
        status_str = "Fully Consumed in Practical / Lab"
    elif damaged_qty > 0 or missing_qty > 0:
        status_str = "Returned with Issues / Defect Recorded"
    else:
        status_str = "Acknowledged / Partially Returned & Consumed"

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

def generate_overdue_reminder_whatsapp_message(recipient_name, recipient_id, component_name, quantity, unit, expected_return_date, lab_name="Embedded Systems Laboratory"):
    """Create an urgent WhatsApp reminder for overdue laboratory equipment."""
    title = f"SVPCET NAGPUR (IIoT) - OVERDUE EQUIPMENT REMINDER"
    greeting = f"Attention: *{recipient_name}*"
    if recipient_id:
        greeting += f" (UID/ID: *{recipient_id}*)"

    msg = (
        f"🏛 *{title}*\n\n"
        f"{greeting},\n\n"
        f"⚠️ This is an urgent reminder that the following laboratory equipment is currently *OVERDUE* for return:\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Item:* {component_name}\n"
        f"🔢 *Quantity:* {quantity} {unit}\n"
        f"⏰ *Due Date was:* {expected_return_date or 'Immediate'}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Please return this equipment to the *{lab_name}* immediately to ensure availability for other students.\n\n"
        f"— *{lab_name}, Dept. of Industrial IoT*\n"
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


def get_whatsapp_business_intent_url(phone, message_text):
    """Generate Android Intent URI specifically targeting WhatsApp Business (com.whatsapp.w4b)."""
    clean_phone = format_phone_number(phone)
    if not clean_phone:
        return ""
    encoded_text = urllib.parse.quote(message_text)
    return f"intent://send?phone={clean_phone}&text={encoded_text}#Intent;package=com.whatsapp.w4b;scheme=whatsapp;end"

def get_whatsapp_regular_intent_url(phone, message_text):
    """Generate Android Intent URI specifically targeting Regular WhatsApp (com.whatsapp)."""
    clean_phone = format_phone_number(phone)
    if not clean_phone:
        return ""
    encoded_text = urllib.parse.quote(message_text)
    return f"intent://send?phone={clean_phone}&text={encoded_text}#Intent;package=com.whatsapp;scheme=whatsapp;end"
