from django.db import models
from django.utils.html import format_html

class FileUploadHistory(models.Model):
    user = models.CharField(max_length=255)
    upload_time = models.DateTimeField(auto_now_add=True)
    input_file = models.FileField(upload_to='uploads/')
    graph_url = models.CharField(max_length=255 , blank=True, null=True)

    def input_file_link(self):
        if self.input_file:
            return format_html('<a href="{}" download>{}</a>', self.input_file.url, self.input_file.name)
        return "No file uploaded"

    def __str__(self):
        return f'{self.user} - {self.upload_time}'

    class Meta:
        verbose_name_plural = 'File Upload History'
