
from qfluentwidgets import FluentIcon

def file_type_icon(file_type: str):
    icon = FluentIcon.DOCUMENT
    if file_type in ["mp4", "flv", "f4v", "webm", "m4v", "mov", "3gp", "3g2", "rm", "rmvb", "wmv", "avi",
                                  "asf", "mpg", "mpeg", "mpe", "ts", "div", "dv", "divx", "dat"]:
        icon = FluentIcon.VIDEO
    elif file_type in ["mp3", "wav", "ogg", "aac", "flac", "wma", "m4a", "m4b"]:
        icon = FluentIcon.MEDIA
    elif file_type in ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "psd", "ai", "svg"]:
        icon = FluentIcon.PHOTO
    elif file_type in ["zip", "rar", "7z", "tar", "gz", "bz2", "xz"]:
        icon = FluentIcon.ZIP_FOLDER
    elif file_type in ["exe", "msi", "bat", "sh", "cmd", "ps1"]:
        icon = FluentIcon.COMMAND_PROMPT
    elif file_type in ["html", "htm", "xhtml", "css", "js", "php", "py", "java", "c", "cpp", "h",
                                    "hpp", "swift", "go", "rs", "rb", "pl", "json", "xml", "yaml", "yml", "md"]:
        icon = FluentIcon.CODE

    return icon