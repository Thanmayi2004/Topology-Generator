from django.contrib import admin
from .models import FileUploadHistory

@admin.register(FileUploadHistory)
class FileUploadHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'upload_time', 'input_file_link', 'graph_url')
    readonly_fields = ('input_file_link',)