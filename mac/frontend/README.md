# ILGC Research - Personlising Workplace Productivity by Eliminating Distractions

## Project Overview

This is a research web-application for the ILGC (Innovation Lab and Grand Chanllenges) project, designed to collect task assessment data including NASA TLX workload ratings and user experience feedback for our system.

## How can I edit this code?

There are several ways of editing your application.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## How can I deploy this project?

This project can be deployed to any static hosting service such as:

- **Vercel**: Connect your GitHub repository and deploy automatically
- **Netlify**: Drag and drop your build folder or connect your repository
- **GitHub Pages**: Use GitHub Actions to build and deploy
- **AWS S3 + CloudFront**: For enterprise deployments

## Build and Deploy

```sh
# Build the project for production
npm run build

# Preview the production build locally
npm run preview
```

The built files will be in the `dist/` directory, ready for deployment.
