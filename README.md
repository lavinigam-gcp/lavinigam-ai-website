# Personal Website

This is my personal website built with [Hugo](https://gohugo.io/) and the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme, hosted on GitHub Pages.

## Quick Start

### Local Development

1. Install Hugo (if not already installed):
   ```bash
   brew install hugo
   ```

2. Clone the repository with submodules:
   ```bash
   git clone --recurse-submodules https://github.com/lavinigam/lavinigam-ai-website.git
   cd lavinigam-ai-website
   ```

3. Run the development server:
   ```bash
   hugo server -D
   ```

4. Open your browser to `http://localhost:1313`

### Creating New Content

Create a new blog post:
```bash
hugo new posts/my-post-name.md
```

Create a new page:
```bash
hugo new page-name.md
```

### Building for Production

Build the site:
```bash
hugo --minify
```

The static files will be generated in the `public/` directory.

## Deployment

This site is automatically deployed to GitHub Pages using GitHub Actions. Every push to the `main` branch triggers a new deployment.

### GitHub Pages Setup

1. Go to your repository settings
2. Navigate to Pages section
3. Set Source to "GitHub Actions"
4. The site will be available at `https://lavinigam.github.io/`

### Custom Domain Setup

To use a custom domain:

1. Update `baseURL` in `hugo.yaml` to your custom domain
2. Add your domain to `static/CNAME` file (replace the placeholder)
3. In GitHub repository settings > Pages, add your custom domain
4. Configure DNS records with your domain provider:
   - For apex domain (example.com): Add A records pointing to GitHub Pages IPs
   - For subdomain (www.example.com): Add CNAME record pointing to `lavinigam.github.io`

GitHub Pages IPs:
```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

## Configuration

Main configuration file: `hugo.yaml`

Key settings to customize:
- `baseURL`: Your site URL
- `title`: Site title
- `params.author`: Your name
- `params.description`: Site description
- `params.socialIcons`: Your social media links
- `params.homeInfoParams`: Homepage content

## Theme

This site uses the PaperMod theme, added as a git submodule.

To update the theme:
```bash
git submodule update --remote --merge
```

## Directory Structure

```
.
├── archetypes/          # Content templates
├── content/             # Your content (posts, pages)
│   ├── posts/          # Blog posts
│   ├── about.md        # About page
│   ├── archives.md     # Archives page
│   └── search.md       # Search page
├── static/              # Static files (images, CNAME, etc.)
├── themes/              # Hugo themes
│   └── PaperMod/       # PaperMod theme (git submodule)
├── .github/
│   └── workflows/      # GitHub Actions workflows
├── hugo.yaml           # Main configuration file
└── README.md           # This file
```

## Resources

- [Hugo Documentation](https://gohugo.io/documentation/)
- [PaperMod Documentation](https://github.com/adityatelange/hugo-PaperMod/wiki)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

## License

Content is copyrighted. Theme is licensed under MIT.
