#!/usr/bin/env python3
# vim: set noet ts=4 sts=4 sw=4:

import sys,os
from sh import convert, git, mkdir

# Yay OS X vs Linux
try:
	from sh import gcp as cp
except ImportError:
	from sh import cp

# n.b. remaining imports in __main__ gaurd below

def md_to_html(src_path, dst_path, md_file):
	page = os.path.splitext(md_file)[0]
	with open('html/{}.html'.format(os.path.join(dst_path, page)), 'w') as o:
		logger.info('Rendering ' + md_file)
		content = markdown.markdown(open(os.path.join(src_path, md_file)).read(),
				extensions=['extra', 'toc', 'md_in_html',
					ImgToPictureExtension()])
		o.write(header_tmpl.render(active_page=page, content=content))

def class_md_to_html(src_path, dst_path, md_file, meta):
	page = os.path.splitext(md_file)[0]
	with open('html/{}.html'.format(os.path.join(dst_path, page)), 'w') as o:
		logger.info('Rendering for class ' + md_file)
		content = markdown.markdown(open(os.path.join(src_path, md_file)).read(),
				extensions=['extra', 'toc', 'md_in_html'])
		title = '{} - {} {}'.format(meta['course'].upper(), meta['quarter'].title(), meta['year'])
		o.write(header_class_tmpl.render(content=content, title=title))

# Process worker fn
def _gen_web_image(spath, dpaths):
	for dpath in dpaths:
		convert(spath, dpath)

def gen_web_images(spath, dpath):
	# First, see what of this we can skip
	# This abuses exceptions a bit for control flow; w/e it's a script
	sstat = os.stat(spath)

	# Copy original image
	try:
		dstat = os.stat(dpath)
		if sstat.st_mtime > dstat.st_mtime:
			# Copy original, it's newer
			raise FileNotFoundError
	except FileNotFoundError:
		cp('-u', '--reflink=auto', spath, dpath)

	# Create web-optimized versions
	basename = os.path.splitext(dpath)[0]
	dpaths = list()
	try:
		avstat = os.stat(basename + '.avif')
		if sstat.st_mtime > avstat.st_mtime:
			logger.debug('Updated img will need AVIF ' + spath)
			raise FileNotFoundError
	except FileNotFoundError:
		logger.debug('Creating AVIF for ' + spath)
		dpaths.append(basename + '.avif')
	try:
		wmsat = os.stat(basename + '.webp')
		if sstat.st_mtime > wmsat.st_mtime:
			logger.info('Updated img will need WebP ' + spath)
			raise FileNotFoundError
	except FileNotFoundError:
		logger.debug('Creating WebP for ' + spath)
		dpaths.append(basename + '.webp')
	if dpaths:
		WORKER_JOBS.append(WORKER_POOL.apply_async(_gen_web_image, (spath, dpaths)))

static_extensions = [
		'.css', '.js', '.ico', '.ttf', '.eot', '.svg', '.woff',
		'.pdf', '.pptx', '.doc', '.docx', '.txt',
		'.gz', '.tgz', '.otf', '.odp', '.webmanifest', '.xml',
		'.h', '.c', '.cpp', '.cxx', '.mk', '.ipynb',
		'.zip', '.webm', '.patch',
		]
image_extensions = [
		'.png', '.jpg',
		]

def handle_static_file(spath, dpath):
	#logger.debug('Static: {} -> {}'.format(spath, dpath))
	ext = os.path.splitext(dpath)[1]

	if ext in image_extensions:
		gen_web_images(spath, dpath)
	elif ext in static_extensions:
		# These do not need to be compiled in any way
		# Just copy them
		#
		# n.b. this assumes linux-like cp (gcp import)
		cp('-u', '--reflink=auto', spath, dpath)
	else:
		logger.debug('Skipping file (ext >>{}<<): {}'.format(ext, spath))


# Prevent recursion in multiprocess case
if __name__ == '__main__':
	import jinja2 as jinja
	import markdown

	import logger
	import publications

	from ImgToPictureTreeprocessor import ImgToPictureExtension

	from multiprocessing import Pool
	global WORKER_POOL
	global WORKER_JOBS
	WORKER_POOL = Pool()
	WORKER_JOBS = list()

	jinja_env = jinja.Environment(loader=jinja.FileSystemLoader('templates'))

	header_tmpl = jinja_env.get_template('header.html')
	header_class_tmpl = jinja_env.get_template('header_class.html')
	footer_tmpl = jinja_env.get_template('footer.html')

	pubs_groups   = publications.init(jinja_env)

	mkdir('-p', 'html')

	for md in os.listdir('pages'):
		if md[-3:] == '.md':
			md_to_html('pages', '/', md)

	logger.info('Process classes')
	for year in os.listdir('classes'):
		if year.startswith('.'):
			continue
		logger.info('  Process ' + year)
		mkdir('-p', os.path.join('html', 'classes', year))

		for quarter in os.listdir(os.path.join('classes', year)):
			if quarter.startswith('.'):
				continue
			logger.info('    Process ' + quarter)
			mkdir('-p', os.path.join('html', 'classes', year, quarter))

			for course in os.listdir(os.path.join('classes', year, quarter)):
				if course.startswith('.'):
					continue
				logger.info('      Process ' + course)
				mkdir('-p', os.path.join('html', 'classes', year, quarter, course))

				for filename in os.listdir(os.path.join('classes', year, quarter, course)):
					if filename.startswith('.'):
						continue
					if filename.startswith('~'):
						continue
					if filename[-3:] == '.md':
						logger.info('        Process ' + filename)
						path = os.path.join('classes', year, quarter, course)
						meta = {
								'year': year,
								'quarter': quarter,
								'course': course,
								}
						class_md_to_html(path, path, filename, meta)
					else:
						spath = os.path.join('classes', year, quarter, course, filename)
						dpath = os.path.join('html', spath)
						handle_static_file(spath, dpath)

				# Hacks on hacks on hacks on hacks
				if os.path.isdir(os.path.join('classes', year, quarter, course, 'video')):
					for filename in os.listdir(os.path.join('classes', year, quarter, course, 'video')):
						mkdir('-p', os.path.join('html', 'classes', year, quarter, course, 'video'))
						spath = os.path.join('classes', year, quarter, course, 'video', filename)
						dpath = os.path.join('html', spath)
						handle_static_file(spath, dpath)

				# Hacks on hacks on hacks on hacks on hacks on hacks
				if os.path.isdir(os.path.join('classes', year, quarter, course, 'assignment2')):
					for filename in os.listdir(os.path.join('classes', year, quarter, course, 'assignment2')):
						mkdir('-p', os.path.join('html', 'classes', year, quarter, course, 'assignment2'))
						if filename.startswith('.'):
							continue
						if filename.startswith('~'):
							continue
						if filename[-3:] == '.md':
							logger.info('        Process ' + filename)
							path = os.path.join('classes', year, quarter, course, 'assignment2')
							meta = {
									'year': year,
									'quarter': quarter,
									'course': course,
									}
							class_md_to_html(path, path, filename, meta)
						else:
							spath = os.path.join('classes', year, quarter, course, 'assignment2', filename)
							dpath = os.path.join('html', spath)
							handle_static_file(spath, dpath)

	logger.info('Building publications database...')
	publications.generate_publications_page(pubs_groups, jinja_env)

	# Put all static content in the html folder
	logger.info('Copying static content...')
	for dirpath,dirnames,filenames in os.walk('static'):

		# Create the mirrored folders in the html directory
		if len(dirnames) > 0:
			for dirname in dirnames:
				path = os.path.join(dirpath, dirname)
				path = 'html' + path[6:] # now that there is a hack
				mkdir('-p', path)


		if len(filenames) > 0:
			for filename in filenames:
				spath = os.path.join(dirpath, filename)
				# hack hack hack
				assert spath[:7] == 'static/'
				dpath = os.path.join('html', spath[7:])
				assert(dpath[:4] == 'html')
				handle_static_file(spath, dpath)

	logger.info("Waiting for any outstanding tasks to complete...")
	# Get any errors from jobs (makes join redudant but :shrug:)
	while WORKER_JOBS:
		j = WORKER_JOBS.pop(0)
		if not j.ready():
			logger.info("...waiting for {} jobs".format(len(WORKER_JOBS)))
		j.get()
	WORKER_POOL.close()
	WORKER_POOL.join()

	logger.info("Done!")
