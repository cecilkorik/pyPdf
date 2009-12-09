# vim: sw=4:expandtab:foldmethod=marker
#
# Copyright (c) 2006, Mathieu Fenniak
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from generic import *
from pdf import PdfFileReader, PdfFileWriter

class _MergedPage(object):
    """
    _MergedPage is used internally by PdfFileMerger to collect necessary information on each page that is being merged.
    """
    def __init__(self, pagedata, src, id):
        self.src = src
        self.pagedata = pagedata
        self.id = id
        
class PdfFileMerger(object):
    """
    PdfFileMerger merges multiple PDFs into a single PDF. It can concatenate, 
    slice, insert, or any combination of the above.
    
    See the functions "merge" (or "append") and "write" (or "overwrite") for
    usage information.
    """
    
    def __init__(self):
        """
        >>> PdfFileMerger()
        
        Initializes a PdfFileMerger, no parameters required
        """
        self.inputs = []
        self.pages = []
        self.output = PdfFileWriter()
        self.bookmarks = []
        self.id_count = 0
        
    def merge(self, position, fileobj, bookmark=None, pages=None):
        """
        >>> merge(position, file, bookmark=None, pages=None)
        
        Merges the pages from the source document specified by "file" into the output
        file at the page number specified by "position".
        
        Optionally, you may specify a bookmark to be applied at the beginning of the 
        included file by supplying the text of the bookmark in the "bookmark" parameter.
        
        You may also use the "pages" parameter to merge only the specified range of 
        pages from the source document into the output document.
        """
        
        my_file = False
        if type(fileobj) in (str, unicode):
            fileobj = file(fileobj, 'rb')
            my_file = True
            
        if type(fileobj) == PdfFileReader:
            pdfr = fileobj
            fileobj = pdfr.file
        else:
            pdfr = PdfFileReader(fileobj)
        
        # Find the range of pages to merge
        if pages == None:
            pages = (0, pdfr.getNumPages())
        elif type(pages) in (int, float, str, unicode):
            raise TypeError('"pages" must be a tuple of (start, end)')
        
        srcpages = []
        
        if bookmark:
            bookmark = {'/Type': '/Fit', '/Page': NumberObject(self.id_count), '/Title': bookmark}
        
        outline = pdfr.getOutlines()
        outline = self._trim_outline(pdfr, outline, pages)
        
        if bookmark:
            self.bookmarks += [bookmark, outline]
        else:
            self.bookmarks += outline
        
        # Gather all the pages that are going to be merged
        for i in range(*pages):
            pg = pdfr.getPage(i)
            
            id = self.id_count
            self.id_count += 1
            
            mp = _MergedPage(pg, pdfr, id)
            
            srcpages.append(mp)

        self._associate_bookmarks_to_pages(srcpages)
            
        
        # Slice to insert the pages at the specified position
        self.pages[position:position] = srcpages
        
        # Keep track of our input files so we can close them later
        self.inputs.append((fileobj, pdfr, my_file))
        
        
    def append(self, fileobj, bookmark=None, pages=None):
        """
        >>> append(file, bookmark=None, pages=None):
        
        Identical to the "merge" function, but assumes you want to concatenate all pages
        onto the end of the file instead of specifying a position.
        """
        
        self.merge(len(self.pages), fileobj, bookmark, pages)
        
    
    def write(self, fileobj):
        """
        >>> write(file)
        
        Writes all data that has been merged to "file" (which can be a filename or any
        kind of file-like object)
        """
        my_file = False
        if type(fileobj) in (str, unicode):
            fileobj = file(fileobj, 'wb')
            my_file = True


        # Add pages to the PdfFileWriter
        for page in self.pages:
            self.output.addPage(page.pagedata)

            
        # Once all pages are added, create bookmarks to point at those pages
        self._write_bookmarks()
        
        # Write the output to the file   
        self.output.write(fileobj)
        
        if my_file:
            fileobj.close()


        
    def close(self):
        """
        >>> close()
        
        Shuts all file descriptors (input and output) and clears all memory usage
        """
        self.pages = []
        for fo, pdfr, mine in self.inputs:
            if mine:
                fo.close()
        
        self.inputs = []
        self.output = None
      
    def _trim_outline(self, pdf, outline, pages):
        """
        Removes any outline/bookmark entries that are not a part of the specified page set
        """
        new_outline = []
        prev_header_added = True
        for i, o in enumerate(outline):
            if type(o) == list:
                sub = self._trim_outline(pdf, o, pages)
                if sub:
                    if not prev_header_added:
                        new_outline.append(outline[i-1])
                    new_outline.append(sub)
            else:
                prev_header_added = False
                for j in range(*pages):
                    if pdf.getPage(j).getObject() == o['/Page'].getObject():
                        o[NameObject('/Page')] = o['/Page'].getObject()
                        new_outline.append(o)
                        prev_header_added = True
                        break
        return new_outline
   
 
    def _write_bookmarks(self, bookmarks=None, parent=None):
        if bookmarks == None:
            bookmarks = self.bookmarks

        last_added = None
        for b in bookmarks:
            if type(b) == list:
                self._write_bookmarks(b, last_added)
                continue
                
            pageno = None
            pdf = None
            if b.has_key('/Page'):
                for i, p in enumerate(self.pages):
                    if p.id == b['/Page']:
                        pageno = i
                        pdf = p.src
            if pageno != None:
                last_added = self.addBookmark(self.output, b['/Title'], pageno, parent)
    
    def _associate_bookmarks_to_pages(self, pages, bookmarks=None):
        if bookmarks == None:
            bookmarks = self.bookmarks

        for b in bookmarks:
            if type(b) == list:
                self._associate_bookmarks_to_pages(pages, b)
                continue
                
            pageno = None
            bp = b['/Page']
            
            if type(bp) == NumberObject:
                continue
                
            for p in pages:
                if bp.getObject() == p.pagedata.getObject():
                    pageno = p.id
            
            if pageno != None:
                b[NameObject('/Page')] = NumberObject(pageno)
            else:
                raise ValueError, "Unresolved bookmark '%s'" % (b['/Title'],)
                
     

    def addBookmark(self, pdf, title, pagenum, parent=None):
    	"""
    	Add a bookmark to the pdf, using the specified title and pointing at 
    	the specified page number. A parent can be specified to make this a
    	nested bookmark below the parent.
    	"""
        pageRef = pdf.getObject(pdf._pages)['/Kids'][pagenum]
        action = DictionaryObject()
        action.update({
            NameObject('/D') : ArrayObject([pageRef, NameObject('/FitH'), NumberObject(826)]),
            NameObject('/S') : NameObject('/GoTo')
        })
        actionRef = pdf._addObject(action)

        root = pdf.getObject(pdf._root)
        if root.has_key('/Outlines'):
            outline = root['/Outlines']
            outlineRef = pdf.getReference(outline)
            lastBookmark = outline['/Last']
        else:
            outline = TreeObject()
            outline.update({
            })
            outlineRef = pdf._addObject(outline)
            root[NameObject('/Outlines')] = outlineRef

        if parent == None:
            parent = outlineRef
            

        bookmark = TreeObject()

        bookmark.update({
            NameObject('/A') : actionRef,
            NameObject('/Title') : createStringObject(title),
        })

        bookmarkRef = pdf._addObject(bookmark)
        bookmark.ref = bookmarkRef
        
        parent = parent.getObject()
        parent.addChild(bookmarkRef, pdf)
        
        return bookmarkRef
