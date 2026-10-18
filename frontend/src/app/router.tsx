import { createBrowserRouter } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { NotFoundPage } from "@/components/NotFoundPage";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AuthCallbackPage } from "@/features/auth/AuthCallbackPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { BookDetailPage } from "@/features/books/BookDetailPage";
import { DiscoverPage } from "@/features/books/DiscoverPage";
import { DiscussionPage } from "@/features/discussion/DiscussionPage";
import { DiscussionStartPage } from "@/features/discussion/DiscussionStartPage";
import { LibraryPage } from "@/features/reading/LibraryPage";
import { ReadingConfigPage } from "@/features/reading/ReadingConfigPage";
import { ReadingPage } from "@/features/reading/ReadingPage";
import { RecommendationsPage } from "@/features/recommendations/RecommendationsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/auth/callback", element: <AuthCallbackPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: "/", element: <DiscoverPage /> },
          { path: "/books/:bookId", element: <BookDetailPage /> },
          { path: "/library", element: <LibraryPage /> },
          { path: "/reading/new", element: <ReadingConfigPage /> },
          { path: "/reading/:readingId", element: <ReadingPage /> },
          { path: "/discussions/new", element: <DiscussionStartPage /> },
          { path: "/discussions/:conversationId", element: <DiscussionPage /> },
          { path: "/recommendations", element: <RecommendationsPage /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);
